# worker.py — RedDust Background Job Runner (MVP: asyncio, no Redis/ARQ)

# Purpose:
#     Provides compute_session_soul_score(), a plain async function that runs
#     at session end to aggregate dimension scores and refresh the soul score
#     snapshot for a user.

# How it's called:
#     At WebSocket disconnect, the session handler fires:
#         asyncio.create_task(compute_session_soul_score(user_id, session_id, pool))

#     This is fire-and-forget — the disconnect handler does NOT await it.

# What it does (in order):
#     1. CALL reddust.refresh_session_dimension_scores(session_id)
#        → Aggregates conversation_dimension_score rows into session_dimension_score
#          using confidence-weighted averaging across all conversations in the session.

#     2. CALL reddust.refresh_soul_score_snapshot(user_id, session_id)
#        → Calls compute_soul_score() internally, which blends current session score
#          with short-term and long-term history using duration-dependent weights.
#          Upserts results into user_soul_score_snapshot.

#     3. extract_preferences_from_session(session_id, user_id, pool)
#        → Reads all transcript_segment rows for the session, sends the full
#          transcript to Gemini Flash for batch preference extraction, and upserts
#          results into user_music_preference + preference_extraction_log.

# Why no ARQ/Redis:
#     For MVP with a small beta cohort, asyncio.create_task() is sufficient.
#     The job is short (~2–3s of DB + Gemini work). If the server restarts
#     mid-job, the soul score for that session is simply not computed — it will
#     be recalculated on the next session from history. ARQ can be added post-MVP
#     when job durability becomes a real requirement.


import asyncio
import logging
import uuid

import asyncpg

# Batch preference extractor — reads full session transcript, calls Gemini Flash,
# upserts preferences into user_music_preference and preference_extraction_log.
from app.services.preference_batch_extractor import extract_preferences_from_session

logger = logging.getLogger(__name__)


async def compute_session_soul_score(
    user_id: str,
    session_id: str,
    pool: asyncpg.Pool,
) -> None:
    """
    Background job: compute and persist soul score for a completed session.

    Called via asyncio.create_task() at session end (WebSocket disconnect).
    Never raises — all exceptions are caught and logged so the event loop
    is not disrupted.

    Args:
        user_id:    UUID string of the user whose session just ended.
        session_id: UUID string of the session that ended.
        pool:       asyncpg connection pool (shared with the FastAPI app).
    """
    logger.info(
        "compute_session_soul_score started | user=%s session=%s",
        user_id, session_id,
    )

    try:
        # ------------------------------------------------------------------
        # Step 1: Aggregate conversation-level dimension scores into a
        #         single session-level score per dimension.
        #
        # Stored procedure: reddust.refresh_session_dimension_scores(p_session_id)
        # - Reads all conversation_dimension_score rows for conversations
        #   that belong to this session.
        # - Computes confidence-weighted average score per dimension.
        # - Upserts results into session_dimension_score.
        # - Excludes invalidated scores (invalidated_at IS NOT NULL).
        # ------------------------------------------------------------------
        async with pool.acquire() as conn:
            await conn.execute(
                "CALL reddust.refresh_session_dimension_scores($1::uuid)",
                session_id,
            )
        logger.info(
            "refresh_session_dimension_scores OK | session=%s", session_id
        )

        # ------------------------------------------------------------------
        # Step 2: Compute duration-weighted soul score and persist snapshot.
        #
        # Stored procedure: reddust.refresh_soul_score_snapshot(p_user_id, p_as_of_session_id)
        # - Calls reddust.compute_soul_score() internally, which blends:
        #     CURRENT    = session_dimension_score for this session
        #     SHORT TERM = prior session scores within config.short_term_days (28d)
        #     LONG TERM  = prior session scores within config.long_term_days (365d)
        #   using per-dimension duration_code weights from soul_score_duration_policy.
        # - Upserts results into user_soul_score_snapshot.
        # - v_user_dashboard_soul_score automatically picks up the new snapshot.
        # ------------------------------------------------------------------
        async with pool.acquire() as conn:
            await conn.execute(
                "CALL reddust.refresh_soul_score_snapshot($1::uuid, $2::uuid)",
                user_id,
                session_id,
            )
        logger.info(
            "refresh_soul_score_snapshot OK | user=%s session=%s",
            user_id, session_id,
        )

        # ------------------------------------------------------------------
        # Step 3: Batch preference extraction from full session transcript.
        #
        # Fetches all transcript_segment rows for the session (ordered by
        # segment_index), concatenates them into a full transcript, and calls
        # Gemini Flash to extract preferences (genre, artist, decade, language,
        # life_situation) including implicit/nuanced signals that per-turn
        # extraction may have missed. Upserts into user_music_preference and
        # writes all extractions to preference_extraction_log.
        # ------------------------------------------------------------------
        await extract_preferences_from_session(
            session_id=uuid.UUID(session_id),
            user_id=uuid.UUID(user_id),
            pool=pool,
        )
        logger.info(
            "extract_preferences_from_session OK | user=%s session=%s",
            user_id, session_id,
        )

    except Exception:
        # Log and swallow — this job must never crash the event loop.
        # The soul score will simply be missing for this session and will
        # be recalculated from history on the next session.
        logger.exception(
            "compute_session_soul_score FAILED | user=%s session=%s",
            user_id, session_id,
        )
