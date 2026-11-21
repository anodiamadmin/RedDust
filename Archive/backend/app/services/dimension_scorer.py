# services/dimension_scorer.py — Conversation dimension scorer (Soul Score trigger)
#
# Responsibility:
#   At the end of each conversation, fetch the full transcript, ask Gemini Flash
#   to score each of the 32 wellbeing dimensions, and write the results to:
#     - conversation_dimension_score  (score per dimension for this conversation)
#     - wellbeing_signal              (high-confidence directional signals, confidence >= 0.75)
#
# How it fits into the flow:
#   WebSocket disconnect handler (Step 36) calls score_conversation_dimensions()
#   → this function feeds conversation_dimension_score rows
#   → ARQ job (Step 33) then calls refresh_session_dimension_scores() +
#     refresh_soul_score_snapshot() stored procedures which aggregate these rows
#     into session-level and user-level soul scores
#
# Design decisions:
#   - Fetches ALL transcript_segment rows for the conversation (both user + syan)
#     so Gemini has full context, not just user turns
#   - Only dimensions with EXPLICIT evidence in the transcript get scored —
#     Gemini is instructed to skip dimensions it cannot ground in the transcript
#   - High-confidence signals (confidence >= 0.75) are also written to wellbeing_signal
#     as directional evidence (-1 = declining, 0 = stable, +1 = improving)
#   - Uses UPSERT on conversation_dimension_score so safe to call multiple times
#   - Fire-and-forget safe: caller can use asyncio.create_task()

import json
import logging
from uuid import UUID

import asyncpg
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

_ALGORITHM_VERSION = "1.0"  # Bump this when scoring logic changes

# Minimum confidence to write a wellbeing_signal row
_SIGNAL_CONFIDENCE_THRESHOLD = 0.75

# ---------------------------------------------------------------------------
# 32 Wellbeing Dimensions — must match seed data in migration_001
# dimension_id matches the SMALLINT PK in wellbeing_dimension table
# ---------------------------------------------------------------------------
_DIMENSIONS = [
    {"id": 1,  "name": "Relaxedness",            "description": "Absence of tension; feeling at ease physically and mentally"},
    {"id": 2,  "name": "Energy",                  "description": "Physical and mental energy levels; absence of tiredness or fatigue"},
    {"id": 3,  "name": "Focus",                   "description": "Ability to sustain attention; absence of distractibility"},
    {"id": 4,  "name": "Positive Mood",            "description": "General positive emotional state; absence of low mood"},
    {"id": 5,  "name": "Emotional Release",        "description": "Ability to process and release emotions; absence of emotional buildup"},
    {"id": 6,  "name": "Joy",                      "description": "Presence of joy and happiness; absence of sadness"},
    {"id": 7,  "name": "Pleasure / Enjoyment",     "description": "Capacity to enjoy experiences; absence of anhedonia"},
    {"id": 8,  "name": "Restfulness",              "description": "Feeling rested and at peace; absence of restlessness"},
    {"id": 9,  "name": "Sleep Readiness",          "description": "Readiness for restful sleep; absence of alertness when rest is needed"},
    {"id": 10, "name": "Calmness",                 "description": "Sense of calm and peace; absence of stress or anxiety"},
    {"id": 11, "name": "Motivation",               "description": "Drive to pursue goals and take action; absence of apathy"},
    {"id": 12, "name": "Emotional Balance",        "description": "Stability of mood; absence of mood instability"},
    {"id": 13, "name": "Sense of Support",         "description": "Feeling supported by others; absence of feeling unsupported"},
    {"id": 14, "name": "Emotional Expression",     "description": "Ability to express emotions freely; absence of suppression"},
    {"id": 15, "name": "Creativity",               "description": "Ability to think creatively and imaginatively; absence of creative block"},
    {"id": 16, "name": "Inspiration",              "description": "Feeling inspired and stimulated; absence of dullness or stagnation"},
    {"id": 17, "name": "Engagement",               "description": "Active involvement and interest in life; absence of disengagement"},
    {"id": 18, "name": "Confidence",               "description": "Sense of self-assurance and competence; absence of insecurity"},
    {"id": 19, "name": "Recovery",                 "description": "Ability to recuperate and restore energy; absence of burnout"},
    {"id": 20, "name": "Social Openness",          "description": "Openness to social interaction; absence of withdrawal"},
    {"id": 21, "name": "Hopefulness",              "description": "Positive expectation about the future; absence of hopelessness"},
    {"id": 22, "name": "Resilience",               "description": "Ability to recover from setbacks; absence of fragility or overwhelm"},
    {"id": 23, "name": "Self-Belief",              "description": "Confidence in one's own abilities; absence of self-doubt"},
    {"id": 24, "name": "Connection",               "description": "Sense of meaningful connection to others; absence of loneliness"},
    {"id": 25, "name": "Belonging",                "description": "Sense of being part of a community; absence of isolation"},
    {"id": 26, "name": "Self-Reflection",          "description": "Ability to reflect on oneself honestly; absence of avoidance"},
    {"id": 27, "name": "Self-Awareness",           "description": "Understanding of one's own emotions and patterns; absence of emotional confusion"},
    {"id": 28, "name": "Consistency",              "description": "Regularity and steadiness in habits and behaviour; absence of irregularity"},
    {"id": 29, "name": "Healthy Routine",          "description": "Adherence to positive daily habits; absence of poor habits"},
    {"id": 30, "name": "Purpose",                  "description": "Sense of direction and meaning in life; absence of aimlessness"},
    {"id": 31, "name": "Meaningfulness",           "description": "Feeling that life has depth and value; absence of emptiness"},
    {"id": 32, "name": "Aesthetic Appreciation",   "description": "Capacity to experience beauty and wonder; absence of emotional numbness"},
]

# Pre-formatted dimension list for the prompt — built once at module load
_DIMENSIONS_PROMPT_BLOCK = "\n".join(
    f"  {d['id']}. {d['name']}: {d['description']}"
    for d in _DIMENSIONS
)

# Map dimension_name → dimension_id for fast lookup when writing to DB
_DIMENSION_NAME_TO_ID: dict[str, int] = {d["name"]: d["id"] for d in _DIMENSIONS}

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SCORING_PROMPT = """\
You are a wellbeing analyst for RedDust, an AI wellbeing companion.

You will be given a conversation transcript between a user and Syan (the AI companion).
Your task is to score the relevant wellbeing dimensions you can observe in this transcript.

IMPORTANT RULES:
- Only score dimensions that have CLEAR evidence in the transcript.
- Do NOT guess or infer from absence. If nothing is said about a dimension, skip it.
- Score on a 0–100 scale where 100 = excellent/positive, 0 = very poor/negative.
  For negative dimensions (Stress Load, Anxiety Level, Sadness, Anger, Loneliness,
  Financial Stress): a HIGH score means the negative state is LOW (i.e. person is doing well).
  Example: Calmness = 20 means the user seems very anxious. Anxiety Level = 20 means
  the user seems very anxious (high anxiety = low score on this negative dimension).
- confidence: how confident you are that this score is accurate, 0.0–1.0.
- direction: +1 if the user seems to be improving during the conversation,
  -1 if declining, 0 if stable or unclear.
- rationale: one line of evidence from the transcript supporting the score.

Wellbeing Dimensions (ID. Name: Description):
{dimensions}

Transcript:
{transcript}

Return ONLY a JSON array. No preamble, no markdown, no explanation. Example:
[
  {{
    "dimension_name": "Calmness",
    "score": 35,
    "confidence": 0.85,
    "direction": -1,
    "rationale": "User said they haven't been able to sleep and feel overwhelmed"
  }},
  {{
    "dimension_name": "Motivation",
    "score": 70,
    "confidence": 0.78,
    "direction": 1,
    "rationale": "User expressed wanting to get back to running despite feeling tired"
  }}
]

If no dimensions are observable, return [].
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def score_conversation_dimensions(
    conversation_id: UUID,
    session_id: UUID,
    user_id: UUID,
    pool: asyncpg.Pool,
) -> None:
    """
    Score all observable wellbeing dimensions for a completed conversation.

    Steps:
      1. Fetch all transcript_segment rows for this conversation (ordered by segment_index)
      2. Build a readable transcript string
      3. Call Gemini Flash to score each observable dimension
      4. Upsert scores into conversation_dimension_score
      5. For high-confidence scores (>= 0.75), also insert into wellbeing_signal

    Safe to call as fire-and-forget via asyncio.create_task().
    Never raises — all exceptions are caught and logged.

    Args:
        conversation_id: UUID of the conversation that just ended
        session_id:      UUID of the current session
        user_id:         UUID of the user
        pool:            asyncpg connection pool (app.state.pool)
    """
    try:
        async with pool.acquire() as conn:

            # ----------------------------------------------------------------
            # Step 1: Fetch transcript segments for this conversation
            # ----------------------------------------------------------------
            rows = await conn.fetch("""
                SELECT speaker, text, segment_index
                FROM reddust.transcript_segment
                WHERE conversation_id = $1
                ORDER BY segment_index ASC
            """, conversation_id)

            if not rows:
                logger.warning(
                    "dimension_scorer: no transcript segments found for conversation=%s — skipping",
                    conversation_id,
                )
                return

            # ----------------------------------------------------------------
            # Step 2: Format transcript for prompt
            # ----------------------------------------------------------------
            transcript_lines = []
            for row in rows:
                speaker_label = "User" if row["speaker"] == "user" else "Syan"
                transcript_lines.append(f"{speaker_label}: {row['text']}")
            transcript_text = "\n".join(transcript_lines)

            # ----------------------------------------------------------------
            # Step 3: Call Gemini Flash to score dimensions
            # ----------------------------------------------------------------
            prompt = _SCORING_PROMPT.format(
                dimensions=_DIMENSIONS_PROMPT_BLOCK,
                transcript=transcript_text,
            )
            response = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",  # enforce JSON-only output
                    temperature=0.1,   # low — scoring should be deterministic
                    max_output_tokens=1024,
                ),
            )

            raw = response.text.strip()

            # Strip markdown fences defensively (despite response_mime_type)
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                scored_dimensions = json.loads(raw)
            except json.JSONDecodeError:
                logger.error(
                    "dimension_scorer: JSON parse failed for conversation=%s. Raw: %s",
                    conversation_id, raw[:300],
                )
                return

            if not isinstance(scored_dimensions, list) or len(scored_dimensions) == 0:
                logger.info(
                    "dimension_scorer: Gemini found no observable dimensions for conversation=%s",
                    conversation_id,
                )
                return

            logger.info(
                "dimension_scorer: Gemini scored %d dimensions for conversation=%s",
                len(scored_dimensions), conversation_id,
            )

            # ----------------------------------------------------------------
            # Step 4 & 5: Write scores to DB
            # ----------------------------------------------------------------
            for item in scored_dimensions:
                dimension_name = item.get("dimension_name", "").strip()
                score          = item.get("score")
                confidence     = float(item.get("confidence", 0.0))
                direction      = int(item.get("direction", 0))
                rationale      = item.get("rationale", "")

                # Validate dimension name against our known list
                dimension_id = _DIMENSION_NAME_TO_ID.get(dimension_name)
                if dimension_id is None:
                    logger.warning(
                        "dimension_scorer: unknown dimension_name '%s' from Gemini — skipping",
                        dimension_name,
                    )
                    continue

                # Validate score range
                try:
                    score = float(score)
                    if not (0 <= score <= 100):
                        raise ValueError(f"score out of range: {score}")
                except (TypeError, ValueError) as e:
                    logger.warning(
                        "dimension_scorer: invalid score for dimension '%s': %s — skipping",
                        dimension_name, e,
                    )
                    continue

                # Validate direction
                if direction not in (-1, 0, 1):
                    direction = 0  # safe default

                # Upsert into conversation_dimension_score
                # PK is (conversation_id, dimension_id) — safe to call multiple times
                await conn.execute("""
                    INSERT INTO reddust.conversation_dimension_score (
                        conversation_id, dimension_id, score, confidence,
                        rationale, algorithm_version, calculated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, now())
                    ON CONFLICT (conversation_id, dimension_id)
                    DO UPDATE SET
                        score             = EXCLUDED.score,
                        confidence        = EXCLUDED.confidence,
                        rationale         = EXCLUDED.rationale,
                        calculated_at     = now(),
                        invalidated_at    = NULL
                """,
                    conversation_id,
                    dimension_id,
                    score,
                    confidence,
                    rationale,
                    "1.0",   # algorithm_version — bump when scoring logic changes
                )

                # Write wellbeing_signal for high-confidence scores only
                # These are directional evidence (-1 declining, 0 stable, +1 improving)
                # used by the soul score stored procedure
                if confidence >= _SIGNAL_CONFIDENCE_THRESHOLD:
                    await conn.execute("""
                        INSERT INTO reddust.wellbeing_signal (
                            user_id, session_id, conversation_id,
                            dimension_id, source_type, raw_score,
                            direction, confidence, observed_at
                        ) VALUES ($1, $2, $3, $4, 'inferred', $5, $6, $7, now())
                    """,
                        user_id,
                        session_id,
                        conversation_id,
                        dimension_id,
                        score,
                        direction,
                        confidence,
                    )

            logger.info(
                "dimension_scorer: completed scoring for conversation=%s user=%s",
                conversation_id, user_id,
            )

    except Exception:
        # Never crash the caller — this is fire-and-forget
        logger.exception(
            "dimension_scorer: unhandled error for conversation=%s", conversation_id
        )