# services/functions/user_context.py — fetch_user_context() function handler
#
# Responsibility:
#   Called by function_dispatcher when Gemini Live invokes fetch_user_context().
#   Queries PostgreSQL for everything Syan needs to personalize a session:
#     1. User profile (display name, timezone, onboarding status)
#     2. Music preferences (genre, artist, decade, etc.)
#     3. Latest soul score per wellbeing dimension
#     4. Recent conversation summaries (last 3 sessions — what was discussed)
#     5. Latest period summary (quarterly/monthly long-arc wellbeing narrative)
#
# Why this matters:
#   Without this, every session is cold-start. Syan can't say "Last time you
#   mentioned feeling stressed about exams — how's that going?" or play music
#   that fits the user's known taste.
#
# Return shape:
#   A flat dict returned as FunctionResponse to Gemini Live. Gemini reads it
#   and uses it to ground its next response. All lists are JSON-serializable.
#
# Failure behaviour:
#   Any DB error returns a partial/empty context — never crashes the session.
#   Gemini will still respond; it just won't have personalization data.
#
# Schema note:
#   Conversation summaries live in conversation_summary (separate table),
#   not a column on conversation. Column is summary_text, not summary.

import logging
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def handle_fetch_user_context(
    pool: asyncpg.Pool,
    user_id: UUID,
) -> dict:
    """
    Fetch all personalization context for a user from PostgreSQL.

    Called by function_dispatcher when Gemini Live invokes fetch_user_context().
    Runs 5 queries in a single acquired connection and assembles one dict.

    Args:
        pool:    asyncpg connection pool (app.state.pool)
        user_id: UUID of the current user

    Returns:
        dict with keys:
            display_name     (str | None)
            timezone         (str | None)
            preferences      (list of {preference_type, preference_value, confidence, source})
            soul_scores      (list of {dimension_name, final_score, duration_code})
            period_summary   ({period_type, period_start, period_end, summary_text} | None)
            recent_sessions  (list of {session_date, summary_text})
        On any error, returns {"error": <message>} so Gemini can handle gracefully.
    """
    context = {
        "display_name":    None,
        "timezone":        None,
        "preferences":     [],
        "soul_scores":     [],
        "recent_sessions": [],
        "period_summary":  None,   # latest long-arc wellbeing summary (weekly/monthly/quarterly/yearly)
    }

    try:
        async with pool.acquire() as conn:

            # ----------------------------------------------------------------
            # 1. User profile — display name + timezone for personalized greeting
            #    and time-of-day awareness (e.g. "good morning" vs "good evening")
            # ----------------------------------------------------------------
            profile = await conn.fetchrow("""
                SELECT display_name, timezone
                FROM reddust.app_user
                WHERE user_id = $1
            """, user_id)

            if profile:
                context["display_name"] = profile["display_name"]
                context["timezone"]     = profile["timezone"]

            # ----------------------------------------------------------------
            # 2. Music preferences — all known taste signals for this user,
            #    ordered by confidence so Gemini weights strong signals first.
            #    Only reads user_music_preference (migration_002 table).
            # ----------------------------------------------------------------
            pref_rows = await conn.fetch("""
                SELECT preference_type, preference_value, confidence, source
                FROM reddust.user_music_preference
                WHERE user_id = $1
                ORDER BY confidence DESC, last_confirmed_at DESC
            """, user_id)

            context["preferences"] = [
                {
                    "preference_type":  r["preference_type"],
                    "preference_value": r["preference_value"],
                    "confidence":       float(r["confidence"]),
                    "source":           r["source"],
                }
                for r in pref_rows
            ]

            # ----------------------------------------------------------------
            # 3. Soul scores — latest active wellbeing dimension scores.
            #    Uses v_user_dashboard_soul_score view (already filters to
            #    active dimensions, picks latest score per dimension).
            #    Gives Syan awareness of the user's emotional baseline.
            # ----------------------------------------------------------------
            score_rows = await conn.fetch("""
                SELECT dimension_name, final_score, duration_code, dashboard_rank
                FROM reddust.v_user_dashboard_soul_score
                WHERE user_id = $1
                ORDER BY dashboard_rank
            """, user_id)

            context["soul_scores"] = [
                {
                    "dimension_name": r["dimension_name"],
                    "final_score":    float(r["final_score"]) if r["final_score"] is not None else None,
                    "duration_code":  r["duration_code"],
                }
                for r in score_rows
            ]

            # ----------------------------------------------------------------
            # 4. Recent sessions — last 3 conversation summaries so Syan can
            #    reference what was discussed previously.
            #
            #    Schema: summaries live in conversation_summary (separate table),
            #    joined via conversation → user_session. Column: summary_text.
            #    Ordered by most recent session first.
            # ----------------------------------------------------------------
            session_rows = await conn.fetch("""
                SELECT
                    us.started_at::DATE      AS session_date,
                    cs.summary_text          AS summary_text
                FROM reddust.user_session us
                JOIN reddust.conversation c
                  ON c.session_id = us.session_id
                JOIN reddust.conversation_summary cs
                  ON cs.conversation_id = c.conversation_id
                WHERE us.user_id = $1
                ORDER BY us.started_at DESC
                LIMIT 3
            """, user_id)

            context["recent_sessions"] = [
                {
                    "session_date": str(r["session_date"]),
                    "summary_text": r["summary_text"],
                }
                for r in session_rows
            ]

            # ----------------------------------------------------------------
            # 5. Period summary — latest long-arc wellbeing narrative.
            #    user_period_summary stores weekly/monthly/quarterly/yearly
            #    AI-generated summaries. The most recent one gives Syan a
            #    multi-week or multi-month picture of the user's journey —
            #    e.g. "This user has been struggling with anxiety and low
            #    motivation over the past quarter but is showing improvement."
            #    NULL if the user has never had a period summary generated.
            # ----------------------------------------------------------------
            period_row = await conn.fetchrow("""
                SELECT period_type, period_start, period_end, summary_text
                FROM reddust.user_period_summary
                WHERE user_id = $1
                ORDER BY generated_at DESC
                LIMIT 1
            """, user_id)

            if period_row:
                context["period_summary"] = {
                    "period_type":  period_row["period_type"],
                    "period_start": str(period_row["period_start"]),
                    "period_end":   str(period_row["period_end"]),
                    "summary_text": period_row["summary_text"],
                }

    except Exception as e:
        logger.exception("handle_fetch_user_context failed for user=%s: %s", user_id, e)
        # Return partial context — don't crash the session
        context["error"] = f"Partial context only — DB error: {str(e)}"

    return context
