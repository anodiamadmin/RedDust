# services/preference_extractor.py — Per-turn music preference extractor
#
# Responsibility: after each user turn, extract explicit music preferences
# and persist them to preference_extraction_log + user_music_preference.
#
# Design decisions:
#   - Only extracts HIGH-CONFIDENCE (>= 0.8) EXPLICIT statements
#     ("I love", "I hate", "I always", "I never", "I prefer")
#   - Hypothetical / indirect statements are ignored
#     ("what if someone liked jazz", "my friend loves classical")
#   - Fire-and-forget: caller uses asyncio.create_task() — never blocks audio relay
#   - Gemini Flash Lite used (cheap, fast — this runs every turn)
#   - On confidence < 0.8: logs to preference_extraction_log but skips upsert
#     into user_music_preference (keeps conclusions table clean)

import json
import logging
from uuid import UUID

import asyncpg
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# Confidence threshold to write into user_music_preference conclusions table
_CONFIDENCE_THRESHOLD = 0.8

# Valid preference types — must match what music_recommender.py understands
_VALID_PREFERENCE_TYPES = {
    "artist",
    "genre",
    "decade",
    "language",
    "life_situation",
    "mood_association",
}

_EXTRACTION_PROMPT = """\
You are a music preference extractor. Given one turn of conversation text, \
extract ONLY explicit, high-confidence music preferences directly stated by the speaker.

Rules:
- Only extract if the speaker uses strong explicit language: love, hate, prefer, \
always, never, can't stand, obsessed with, etc.
- Ignore hypothetical statements ("what if", "maybe", "I think I might").
- Ignore statements about other people ("my friend likes", "everyone loves").
- Ignore vague statements ("I like music", "music is good").
- negative: true means the user dislikes / avoids this preference value.

Valid preference_type values: artist, genre, decade, language, life_situation, mood_association

Return ONLY a JSON array. No preamble, no markdown, no explanation.
If nothing qualifies, return [].

Format:
[
  {
    "preference_type": "artist",
    "preference_value": "AR Rahman",
    "confidence": 0.95,
    "negative": false,
    "evidence_quote": "I really love AR Rahman"
  }
]

Conversation turn:
{turn_text}
"""


async def extract_preferences_from_turn(
    turn_text: str,
    user_id: UUID,
    session_id: UUID,
    conversation_id: UUID,
    turn_id: int,
    pool: asyncpg.Pool,
) -> None:
    """
    Extract music preferences from a single user turn and persist to DB.
    Designed to be called as fire-and-forget via asyncio.create_task().

    Args:
        turn_text:       raw text of the user's turn
        user_id:         current user
        session_id:      current session
        conversation_id: current conversation
        turn_id:         turn_id FK from conversation_turn
        pool:            asyncpg connection pool
    """
    if not turn_text or not turn_text.strip():
        return

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=_EXTRACTION_PROMPT.replace("{turn_text}", turn_text.strip()),
            config=types.GenerateContentConfig(
                temperature=0.1,   # low temp — we want deterministic extraction
                max_output_tokens=512,
            ),
        )

        raw = response.text.strip()

        # Strip markdown fences if model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            extractions = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("preference_extractor: JSON parse failed. Raw: %s", raw[:200])
            return

        if not isinstance(extractions, list) or len(extractions) == 0:
            return  # nothing extracted — normal case

        async with pool.acquire() as conn:
            for item in extractions:
                preference_type = item.get("preference_type", "").strip()
                preference_value = item.get("preference_value", "").strip()
                confidence = float(item.get("confidence", 0.0))
                negative = bool(item.get("negative", False))
                evidence_quote = item.get("evidence_quote", "")

                # Skip invalid preference types
                if preference_type not in _VALID_PREFERENCE_TYPES:
                    logger.warning(
                        "preference_extractor: unknown preference_type '%s' — skipping",
                        preference_type,
                    )
                    continue

                if not preference_value:
                    continue

                # Always log to evidence trail regardless of confidence
                await conn.execute(
                    """
                    INSERT INTO reddust.preference_extraction_log (
                        user_id, session_id, conversation_id, turn_id,
                        preference_type, extracted_value, confidence,
                        extraction_method, raw_evidence, extracted_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
                    """,
                    user_id,
                    session_id,
                    conversation_id,
                    turn_id,
                    preference_type,
                    preference_value,
                    confidence,
                    "per_turn",
                    evidence_quote,
                )

                # Only write conclusions if confidence meets threshold
                if confidence < _CONFIDENCE_THRESHOLD:
                    continue

                # Upsert into user_music_preference
                # If value changes (negative flag flips or value updated),
                # increment override_count and update last_confirmed_at
                await conn.execute(
                    """
                    INSERT INTO reddust.user_music_preference (
                        user_id, preference_type, preference_value,
                        confidence, source, first_observed_at, last_confirmed_at,
                        override_count
                    ) VALUES ($1, $2, $3, $4, 'per_turn', now(), now(), 0)
                    ON CONFLICT (user_id, preference_type, preference_value)
                    DO UPDATE SET
                        confidence       = EXCLUDED.confidence,
                        last_confirmed_at = now(),
                        override_count   = reddust.user_music_preference.override_count + 1
                    """,
                    user_id,
                    preference_type,
                    preference_value,
                    confidence,
                )

                logger.info(
                    "preference_extractor: extracted [%s=%s, confidence=%.2f, negative=%s] for user %s",
                    preference_type, preference_value, confidence, negative, user_id,
                )

    except Exception:
        # Never crash the caller — this is fire-and-forget
        logger.exception("preference_extractor: unhandled error for turn_id=%s", turn_id)