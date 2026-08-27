# services/music_recommender.py — Context-aware music recommendation engine
#
# Responsibility:
#   Given a user_id, session_id, mood and session signals, build a rich context
#   from the database (preferences, soul score, reaction history) and ask
#   Gemini Flash to suggest 2-3 smart YouTube search queries tailored to that user.
#
# Why not just use the mood→query map?
#   The hardcoded map gives every anxious user the same search query regardless
#   of taste. This module replaces that with personalised recommendations grounded
#   in actual user data and real-time session signals from Gemini Live.
#
# How it fits into the flow:
#   Gemini Live calls get_music_recommendation(mood_hint, desired_mood, activity, ...)
#   → function_dispatcher routes to music.py handle_get_music_recommendation()
#   → that calls build_music_recommendation_context() + recommend_tracks() here
#   → gets back 2-3 query strings
#   → passes each to verify_and_fetch_track() (track_verifier.py)
#   → returns verified YouTube tracks to Gemini Live as FunctionResponse
#
# Fallback behaviour:
#   If DB is unavailable, user has no preferences, or Gemini fails →
#   falls back to the hardcoded mood→query map. Never crashes.

import json
import logging
from typing import Optional
from uuid import UUID

import asyncpg
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client — reused across calls (thread-safe, connection-pooled internally)
# ---------------------------------------------------------------------------
_gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Fallback mood→query map — used when context build fails or user has no history
# ---------------------------------------------------------------------------
_FALLBACK_MOOD_QUERY_MAP = {
    "anxious":   "calming anxiety relief music",
    "sad":       "gentle uplifting music for sadness",
    "happy":     "upbeat positive background music",
    "stressed":  "stress relief meditation music",
    "tired":     "relaxing sleep music ambient",
    "angry":     "calming music for anger relief",
    "neutral":   "peaceful background ambient music",
    "motivated": "motivational focus music",
    "focused":   "deep focus concentration music",
    "lonely":    "warm comforting background music",
}
_DEFAULT_FALLBACK_QUERY = "peaceful background ambient music"

# Maximum number of recent recommendations to fetch (to avoid repeating them)
_RECENT_RECOMMENDATION_LIMIT = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def build_music_recommendation_context(
    user_id: UUID,
    session_id: UUID,
    pool: asyncpg.Pool,
) -> dict:
    """
    Fetch everything known about the user that's relevant to music recommendations.

    Queries three sources:
      1. user_music_preference — explicit taste signals (genre, artist, decade, language)
      2. v_user_dashboard_soul_score — latest soul score per active dimension
      3. music_recommendation + music_recommendation_reaction — recent history
         to avoid repeating recently skipped or disliked tracks

    Returns a structured dict. Returns an empty/default dict on any DB error
    so the caller can fall back gracefully.

    Args:
        user_id:    The user's UUID
        session_id: The current session's UUID
        pool:       The asyncpg connection pool (app.state.pool)

    Returns:
        dict with keys: preferences, soul_scores, recent_tracks
    """
    context = {
        "preferences": [],   # list of {preference_type, preference_value, confidence}
        "soul_scores": [],   # list of {dimension_name, final_score, duration_code}
        "recent_tracks": [], # list of {title, rating, skipped, completed}
    }

    try:
        async with pool.acquire() as conn:

            # ----------------------------------------------------------------
            # 1. Music preferences — what the user has explicitly expressed
            # ----------------------------------------------------------------
            pref_rows = await conn.fetch("""
                SELECT preference_type, preference_value, confidence, source
                FROM reddust.user_music_preference
                WHERE user_id = $1
                ORDER BY confidence DESC
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
            # 2. Soul score — latest active dimension scores for this user
            #    Uses the v_user_dashboard_soul_score view (active dims only)
            # ----------------------------------------------------------------
            score_rows = await conn.fetch("""
                SELECT dimension_name, final_score, duration_code, dashboard_rank
                FROM reddust.v_user_dashboard_soul_score
                WHERE user_id = $1
                ORDER BY dashboard_rank
            """, user_id)

            # soul score list comprehension
            context["soul_scores"] = [
                {
                    "dimension_name": r["dimension_name"],
                    "final_score": float(r["final_score"]) if r["final_score"] is not None else None,
                    "duration_code":  r["duration_code"],
                }
                for r in score_rows
            ]

            # ----------------------------------------------------------------
            # 3. Recent recommendations + reactions — avoid repeating bad picks
            #    Fetches last N recommendations for this user with their reactions
            # ----------------------------------------------------------------
            recent_rows = await conn.fetch("""
                SELECT
                    mt.title,
                    mt.provider_track_id,
                    mrr.rating,
                    mrr.skipped,
                    mrr.completed,
                    mrr.played
                FROM reddust.music_recommendation mr
                JOIN reddust.music_track mt ON mt.track_id = mr.track_id
                LEFT JOIN reddust.music_recommendation_reaction mrr
                       ON mrr.recommendation_id = mr.recommendation_id
                WHERE mr.user_id = $1
                ORDER BY mr.recommended_at DESC
                LIMIT $2
            """, user_id, _RECENT_RECOMMENDATION_LIMIT)

            context["recent_tracks"] = [
                {
                    "title":              r["title"],
                    "provider_track_id":  r["provider_track_id"],
                    "rating":             r["rating"],
                    "skipped":            r["skipped"],
                    "completed":          r["completed"],
                }
                for r in recent_rows
            ]

    except Exception as e:
        # DB failure is non-fatal — recommender falls back to mood-only
        logger.error("music_recommender: failed to build context for user=%s: %s", user_id, e)

    return context


async def recommend_tracks(
    user_id: UUID,
    session_id: UUID,
    current_mood_hint: str,
    context: dict,
    desired_mood: Optional[str] = None,
    activity: Optional[str] = None,
    energy_level: Optional[str] = None,
    time_of_day: Optional[str] = None,
    session_goal: Optional[str] = None,
) -> list[dict]:
    """
    Ask Gemini Flash to suggest 2-3 YouTube search queries based on user context
    and real-time session signals passed by Gemini Live.

    Args:
        user_id:           The user's UUID (for logging)
        session_id:        The current session's UUID (for logging)
        current_mood_hint: Current detected mood (e.g. "anxious", "tired") — required
        context:           Output of build_music_recommendation_context()
        desired_mood:      Where the user wants to go emotionally (optional)
        activity:          What the user is doing — study, sleep, workout, etc. (optional)
        energy_level:      low | medium | high (optional)
        time_of_day:       morning | afternoon | evening | night (optional)
        session_goal:      What the user wants to achieve this session (optional)

    Returns:
        list of 1-3 dicts with keys: query_string, desired_outcome, rationale
    """
    # If context is empty (new user, DB failure), fall back immediately
    has_useful_context = (
        context.get("preferences") or context.get("soul_scores")
    )

    if not has_useful_context:
        logger.info(
            "music_recommender: no context for user=%s, using fallback for mood=%s",
            user_id, current_mood_hint
        )
        return _fallback_queries(current_mood_hint)

    # Build the prompt with all available signals
    prompt = _build_prompt(
        mood=current_mood_hint,
        context=context,
        desired_mood=desired_mood,
        activity=activity,
        energy_level=energy_level,
        time_of_day=time_of_day,
        session_goal=session_goal,
    )

    try:
        response = await _gemini_client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                # Force JSON-only output — no preamble, no markdown
                response_mime_type="application/json",
                temperature=0.4,   # Some creativity but not too random
                max_output_tokens=512,
            ),
        )

        raw = response.text.strip()
        recommendations = json.loads(raw)

        # Validate structure — must be a list of dicts with query_string
        if not isinstance(recommendations, list):
            raise ValueError("Gemini returned non-list response")

        validated = []
        for item in recommendations:
            if isinstance(item, dict) and "query_string" in item:
                validated.append({
                    "query_string":    str(item.get("query_string", "")),
                    "desired_outcome": str(item.get("desired_outcome", "")),
                    "rationale":       str(item.get("rationale", "")),
                })

        if not validated:
            raise ValueError("No valid recommendations in Gemini response")

        logger.info(
            "music_recommender: Gemini returned %d queries for user=%s mood=%s",
            len(validated), user_id, current_mood_hint
        )
        return validated[:3]  # Cap at 3

    except Exception as e:
        logger.error(
            "music_recommender: Gemini call failed for user=%s: %s — using fallback",
            user_id, e
        )
        return _fallback_queries(current_mood_hint)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prompt(
    mood: str,
    context: dict,
    desired_mood: Optional[str] = None,
    activity: Optional[str] = None,
    energy_level: Optional[str] = None,
    time_of_day: Optional[str] = None,
    session_goal: Optional[str] = None,
) -> str:
    """
    Build the Gemini Flash prompt for music recommendation.

    Incorporates all available real-time signals alongside the DB context.
    The more signals provided, the more targeted the query suggestions will be.

    The prompt is strict:
      - Returns JSON only (enforced by response_mime_type in the caller)
      - 2-3 YouTube search query strings tailored to the user
      - Each query must be specific enough to surface the right content
        (e.g. "AR Rahman 90s melodic instrumental" not just "Indian music")
    """
    # ----------------------------------------------------------------
    # Section 1: Real-time session signals from Gemini Live
    # Only include lines for signals that were actually provided
    # ----------------------------------------------------------------
    session_lines = [f"Current mood: {mood}"]

    if desired_mood:
        session_lines.append(f"Desired mood (where they want to go): {desired_mood}")
    if activity:
        session_lines.append(f"Activity: {activity}")
    if energy_level:
        session_lines.append(f"Energy level: {energy_level}")
    if time_of_day:
        session_lines.append(f"Time of day: {time_of_day}")
    if session_goal:
        session_lines.append(f"Session goal: {session_goal}")

    session_signals_text = "\n".join(session_lines)

    # ----------------------------------------------------------------
    # Section 2: User preferences from DB
    # ----------------------------------------------------------------
    if context["preferences"]:
        lines = [
            f"  - {p['preference_type']}: {p['preference_value']} (confidence: {p['confidence']:.0%})"
            for p in context["preferences"]
        ]
        preferences_text = "Known music preferences:\n" + "\n".join(lines)
    else:
        preferences_text = "Known music preferences: none yet (new user)"

    # ----------------------------------------------------------------
    # Section 3: Soul scores from DB
    # ----------------------------------------------------------------
    if context["soul_scores"]:
        lines = [
            f"  - {s['dimension_name']}: {s['final_score']}/100"
            for s in context["soul_scores"]
            if s["final_score"] is not None
        ]
        soul_score_text = "Current Soul Score (wellbeing dimensions):\n" + "\n".join(lines)
    else:
        soul_score_text = "Current Soul Score: not yet computed (new user)"

    # ----------------------------------------------------------------
    # Section 4: Recent track reactions from DB
    # ----------------------------------------------------------------
    if context["recent_tracks"]:
        lines = []
        for t in context["recent_tracks"]:
            reaction = "no reaction recorded"
            if t["skipped"]:
                reaction = "skipped"
            elif t["rating"] is not None:
                reaction = f"rated {t['rating']}/5"
            elif t["completed"]:
                reaction = "completed"
            lines.append(f"  - \"{t['title']}\" → {reaction}")
        recent_text = "Recently recommended tracks (avoid repeating skipped/low-rated):\n" + "\n".join(lines)
    else:
        recent_text = "Recently recommended tracks: none"

    return f"""You are Syan, an AI music wellbeing companion. Your job is to suggest YouTube search queries
that will find music perfectly suited to this user's current emotional state and personal taste.

--- SESSION SIGNALS ---
{session_signals_text}

--- USER PROFILE ---
{preferences_text}

{soul_score_text}

{recent_text}

--- INSTRUCTIONS ---
- Suggest exactly 2-3 YouTube search query strings.
- Each query must be specific and searchable (e.g. "AR Rahman relaxing instrumental Hindi" not "Indian music").
- Prioritise the user's known preferences when they align with the mood and activity.
- If a desired_mood is provided, select music that will guide the user FROM their current mood TOWARD the desired mood.
- If a session_goal is provided, shape the music arc to support that goal across multiple tracks.
- If a time_of_day is provided, match the music energy to natural daily rhythms (e.g. avoid high-energy tracks at night).
- Avoid suggesting tracks similar to recently skipped or low-rated ones.
- For each query, provide a desired_outcome (what emotional effect it should have) and a rationale.

Return ONLY a JSON array. No preamble, no markdown. Example format:
[
  {{
    "query_string": "AR Rahman soft melodic instrumental 90s",
    "desired_outcome": "gentle mood lift with familiar nostalgia",
    "rationale": "User loves AR Rahman and 90s music; soft instrumental suits anxious state moving toward calm"
  }}
]"""


def _fallback_queries(mood: str) -> list[dict]:
    """
    Return a single hardcoded query when context build or Gemini call fails.
    This ensures the recommendation pipeline never returns empty-handed.
    """
    query = _FALLBACK_MOOD_QUERY_MAP.get(mood.lower(), _DEFAULT_FALLBACK_QUERY)
    return [{
        "query_string":    query,
        "desired_outcome": f"support {mood} state",
        "rationale":       "fallback — no user context available",
    }]
