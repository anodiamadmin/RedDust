# services/preference_batch_extractor.py — End-of-session batch preference extractor
#
# Responsibility:
#   Called once at session end (via ARQ job in worker.py — Step 33).
#   Reads the full session transcript, sends it to Gemini Flash in one batch,
#   and extracts all music preferences — including implicit and nuanced ones
#   that per-turn extraction would miss.
#
# Why batch instead of just per-turn?
#   Per-turn extraction (preference_extractor.py) catches explicit high-confidence
#   statements turn by turn. It misses:
#     - Implicit preferences ("that felt too heavy" → prefers lighter energy)
#     - Contradictions ("I love jazz" T2, "actually classical" T8) — batch resolves
#       these by taking the later statement as ground truth
#     - Patterns that only emerge across the full conversation arc
#
# Flow:
#   1. Fetch all transcript_segment rows for the session (ordered by segment_index)
#   2. Concatenate into a readable full transcript
#   3. Call Gemini Flash with the full transcript + extraction prompt
#   4. Parse JSON response → list of {preference_type, preference_value, confidence, evidence_quote}
#   5. For each preference:
#      a. Upsert into user_music_preference — overwrites if batch confidence >= existing confidence
#      b. Insert into preference_extraction_log with extraction_method='session_batch'
#
# Called by:
#   ARQ job compute_session_soul_score() in worker.py (Step 33)
#   Never called directly from the audio relay loop — always post-session.

import json
import logging
from uuid import UUID

import asyncpg
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level Gemini client singleton — reused across all calls.
# Must be at module level; instantiating inside async functions causes
# ConnectError (learned from dimension_scorer.py bug).
# ---------------------------------------------------------------------------
_gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Prompt template — instructs Gemini to extract all preferences from the
# full transcript, resolve contradictions, and return structured JSON.
# Uses .replace() not .format() — avoids KeyError on JSON braces in prompt.
# ---------------------------------------------------------------------------
_PROMPT_TEMPLATE = """
You are analyzing a full conversation transcript between a user and Syan, an AI music companion.

Your task: extract ALL music preferences expressed by the user — both explicit and implicit.

Rules:
1. Extract preferences for these types ONLY:
   genre, artist, language, decade, energy_level, vocal_style, instrument, life_situation, mood_association
2. If the user contradicts themselves, the LATER statement wins.
3. Only extract preferences about the USER — ignore anything Syan said.
4. Include implicit preferences (e.g. "that felt too heavy" → energy_level: low preferred).
5. Only include preferences with confidence >= 0.6.
6. Return a JSON array. Each item must have exactly these keys:
   - preference_type  (string — one of the types above)
   - preference_value (string — the actual value, e.g. "jazz", "Hindi", "1990s")
   - confidence       (float between 0.0 and 1.0)
   - evidence_quote   (string — the exact user quote that supports this)
7. If no preferences found, return an empty array: []
8. Return ONLY the JSON array. No explanation, no markdown, no backticks.

TRANSCRIPT:
__TRANSCRIPT__
"""


def _build_prompt(transcript: str) -> str:
    """Inject the transcript into the prompt template."""
    return _PROMPT_TEMPLATE.replace("__TRANSCRIPT__", transcript)


def _format_transcript(segments: list[dict]) -> str:
    """
    Format transcript_segment rows into a readable string for Gemini.
    Each line: '[User]: text' or '[Syan]: text'
    """
    lines = []
    for seg in segments:
        speaker = "User" if seg["speaker"] == "user" else "Syan"
        lines.append(f"[{speaker}]: {seg['text']}")
    return "\n".join(lines)


async def extract_preferences_from_session(
    session_id: UUID,
    user_id: UUID,
    pool: asyncpg.Pool,
) -> None:
    """
    Extract music preferences from the full session transcript using Gemini Flash.

    Fetches all transcript_segment rows for the session, sends the full
    transcript to Gemini Flash in one batch, and upserts results into
    user_music_preference + preference_extraction_log.

    Args:
        session_id: UUID of the session to process
        user_id:    UUID of the user who owns the session
        pool:       asyncpg connection pool

    Returns:
        None — writes directly to DB. Never raises — logs errors and returns
        gracefully so session end is never blocked by preference extraction.
    """
    try:
        async with pool.acquire() as conn:

            # ----------------------------------------------------------------
            # Step 1: Fetch full transcript for this session.
            # Ordered by segment_index so the conversation reads chronologically.
            # Only fetch user + syan turns (speaker IN ('user', 'syan')).
            # ----------------------------------------------------------------
            segments = await conn.fetch(
                """
                SELECT speaker, text, segment_index
                FROM reddust.transcript_segment
                WHERE session_id = $1
                ORDER BY segment_index ASC
                """,
                session_id,
            )

            if not segments:
                logger.info(
                    "extract_preferences_from_session: no transcript segments for session=%s — skipping",
                    session_id,
                )
                return

            # ----------------------------------------------------------------
            # Step 2: Format transcript into readable text for Gemini.
            # ----------------------------------------------------------------
            transcript_text = _format_transcript([dict(s) for s in segments])
            prompt = _build_prompt(transcript_text)

            # ----------------------------------------------------------------
            # Step 3: Call Gemini Flash for batch extraction.
            # response_mime_type=application/json forces structured JSON output.
            # temperature=0.1 keeps extraction deterministic.
            # ----------------------------------------------------------------
            response = await _gemini_client.aio.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )

            raw_json = response.text.strip()

            # ----------------------------------------------------------------
            # Step 4: Parse the JSON response.
            # ----------------------------------------------------------------
            try:
                preferences = json.loads(raw_json)
            except json.JSONDecodeError:
                logger.error(
                    "extract_preferences_from_session: invalid JSON from Gemini for session=%s: %s",
                    session_id,
                    raw_json[:200],
                )
                return

            if not isinstance(preferences, list):
                logger.error(
                    "extract_preferences_from_session: expected list, got %s for session=%s",
                    type(preferences).__name__,
                    session_id,
                )
                return

            if not preferences:
                logger.info(
                    "extract_preferences_from_session: no preferences extracted for session=%s",
                    session_id,
                )
                return

            # ----------------------------------------------------------------
            # Step 5: Upsert each preference into DB.
            # user_music_preference: PK is (user_id, preference_type, preference_value).
            # On conflict — update confidence and last_confirmed_at only if the
            # new batch confidence is higher than what's already stored.
            # This ensures batch extraction (which sees the full picture) can
            # override per-turn extraction (which only saw one turn at a time).
            # ----------------------------------------------------------------
            for pref in preferences:
                preference_type  = pref.get("preference_type")
                preference_value = pref.get("preference_value")
                confidence       = pref.get("confidence", 0.0)
                evidence_quote   = pref.get("evidence_quote", "")
                                # Skip malformed entries
                if not preference_type or not preference_value:
                    logger.warning(
                        "extract_preferences_from_session: skipping malformed preference: %s",
                        pref,
                    )
                    continue

                # Skip low-confidence extractions
                if confidence < 0.6:
                    continue

                # Upsert into user_music_preference
                await conn.execute(
                    """
                    INSERT INTO reddust.user_music_preference
                        (user_id, preference_type, preference_value,
                         confidence, source, first_observed_at, last_confirmed_at, override_count)
                    VALUES
                        ($1, $2, $3, $4, 'session_batch', now(), now(), 0)
                    ON CONFLICT (user_id, preference_type, preference_value)
                    DO UPDATE SET
                        confidence        = GREATEST(EXCLUDED.confidence, reddust.user_music_preference.confidence),
                        last_confirmed_at = now(),
                        override_count    = reddust.user_music_preference.override_count + 1
                    """,
                    user_id,
                    preference_type,
                    preference_value,
                    confidence,
                )

                # Log the extraction evidence for auditability
                await conn.execute(
                    """
                    INSERT INTO reddust.preference_extraction_log
                        (user_id, session_id, preference_type, extracted_value,
                         confidence, extraction_method, raw_evidence, extracted_at)
                    VALUES
                        ($1, $2, $3, $4, $5, 'session_batch', $6, now())
                    """,
                    user_id,
                    session_id,
                    preference_type,
                    preference_value,
                    confidence,
                    evidence_quote,
                )

            logger.info(
                "extract_preferences_from_session: extracted %d preferences for session=%s user=%s",
                len(preferences),
                session_id,
                user_id,
            )

    except Exception as e:
        # Never block session end — log and return gracefully
        logger.exception(
            "extract_preferences_from_session failed for session=%s user=%s: %s",
            session_id,
            user_id,
            e,
        )