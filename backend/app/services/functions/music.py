# services/functions/music.py — Music recommendation function handler
#
# Responsibility: orchestrate the full music recommendation pipeline for Gemini Live.
#
# Flow:
#   1. build_music_recommendation_context() — fetch user preferences + soul score + reaction history
#   2. recommend_tracks() — Gemini Flash generates 2-3 personalised query strings
#   3. verify_and_fetch_track() — YouTube API verifies each query, returns public+embeddable track
#   4. Upsert verified tracks into music_track table
#   5. Insert music_recommendation rows with rank + rationale
#   6. Return list of {title, url, thumbnail, duration_ms, artist, rationale} as FunctionResponse

import asyncio
import logging
from uuid import UUID

import asyncpg

from app.services.music_recommender import build_music_recommendation_context, recommend_tracks
from app.services.track_verifier import verify_and_fetch_track

logger = logging.getLogger(__name__)

# YouTube watch URL base
_YT_WATCH_BASE = "https://www.youtube.com/watch?v="


async def handle_get_music_recommendation(
    args: dict,
    user_id: UUID,
    session_id: UUID,
    conversation_id: UUID,
    turn_id: int,
    pool: asyncpg.Pool,
) -> dict:
    """
    Full music recommendation handler called by function_dispatcher when Gemini Live
    invokes get_music_recommendation().

    Args:
        args:            function call args from Gemini Live (expects 'mood_hint' key)
        user_id:         current user
        session_id:      current session
        conversation_id: current conversation
        turn_id:         current turn number
        pool:            asyncpg connection pool

    Returns:
        dict with key 'tracks': list of recommended track dicts, or 'error' on failure.
        Gemini Live reads track titles aloud; frontend handles playback via url.
    """
    mood_hint = args.get("mood_hint", "neutral")

    try:
        # Step 1: build user context (preferences + soul score + recent reactions)
        context = await build_music_recommendation_context(user_id, session_id, pool)

        # Step 2: Gemini Flash generates personalised query strings
        recommendations = await recommend_tracks(
            user_id=user_id,
            session_id=session_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            current_mood_hint=mood_hint,
            pool=pool,
        )

        if not recommendations:
            return {"error": "Could not generate music recommendations."}

        # Step 3: verify each query string against YouTube API concurrently
        verify_tasks = [
            verify_and_fetch_track(rec["query_string"], pool)
            for rec in recommendations
        ]
        verified_tracks = await asyncio.gather(*verify_tasks, return_exceptions=True)

        # Step 4 & 5: upsert tracks + insert recommendation rows, build response
        result_tracks = []
        rank = 1

        async with pool.acquire() as conn:
            for rec, track in zip(recommendations, verified_tracks):
                # Skip failed verifications
                if isinstance(track, Exception) or track is None:
                    logger.warning("Track verification failed for query: %s", rec.get("query_string"))
                    continue

                # Upsert into music_track
                music_track_id = await conn.fetchval(
                    """
                    INSERT INTO reddust.music_track
                        (provider, provider_track_id, title, artist, thumbnail_url, duration_ms, track_url)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (provider, provider_track_id)
                    DO UPDATE SET
                        title        = EXCLUDED.title,
                        artist       = EXCLUDED.artist,
                        thumbnail_url= EXCLUDED.thumbnail_url,
                        duration_ms  = EXCLUDED.duration_ms,
                        track_url    = EXCLUDED.track_url
                    RETURNING id
                    """,
                    track["provider"],
                    track["provider_track_id"],
                    track["title"],
                    track.get("channel_title"),
                    track.get("thumbnail_url"),
                    track.get("duration_ms"),
                    track["track_url"],
                )

                # Insert music_recommendation row
                await conn.execute(
                    """
                    INSERT INTO reddust.music_recommendation
                        (session_id, conversation_id, turn_id, music_track_id, rank,
                         rationale, recommendation_context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    session_id,
                    conversation_id,
                    turn_id,
                    music_track_id,
                    rank,
                    rec.get("rationale"),
                    rec.get("desired_outcome"),
                )

                result_tracks.append({
                    "title":       track["title"],
                    "url":         track["track_url"],
                    "thumbnail":   track.get("thumbnail_url"),
                    "duration_ms": track.get("duration_ms"),
                    "artist":      track.get("channel_title"),
                    "rationale":   rec.get("rationale"),
                })

                rank += 1

        if not result_tracks:
            return {"error": "No verified tracks found. Please try again."}

        return {"tracks": result_tracks}

    except Exception as e:
        logger.exception("handle_get_music_recommendation failed: %s", e)
        return {"error": f"Music recommendation failed: {str(e)}"}















# # services/functions/music.py — Music recommendation function handler
# #
# # Responsibility: given a mood string from Gemini Live, search YouTube Data API
# # for a relevant track and return the top result's title + URL.
# #
# # Why YouTube Data API?
# #   - Free tier (10,000 units/day) is sufficient for a wellness app
# #   - No licensing issues — we return a URL, not the audio itself
# #   - Wide catalogue covering ambient, classical, nature sounds, etc.
# #
# # How this fits into the session:
# #   - Gemini Live calls get_music_recommendation(mood="anxious")
# #   - function_dispatcher routes here
# #   - We query YouTube, return {title, url}
# #   - Gemini reads the title aloud and the frontend handles playback via the URL
# #
# # Mood → search query mapping:
# #   - We don't pass the raw mood directly to YouTube (e.g. "anxious" returns
# #     unpredictable results). Instead we map moods to curated search terms that
# #     reliably surface calming/appropriate content.

# import httpx
# from app.config import settings

# # Curated search terms per mood — tuned for wellness/ambient content
# # Add more moods here as the product evolves
# _MOOD_QUERY_MAP = {
#     "anxious":   "calming anxiety relief music",
#     "sad":       "gentle uplifting music for sadness",
#     "happy":     "upbeat positive background music",
#     "stressed":  "stress relief meditation music",
#     "tired":     "relaxing sleep music ambient",
#     "angry":     "calming music for anger relief",
#     "neutral":   "peaceful background ambient music",
#     "motivated": "motivational focus music",
# }

# # Fallback search term if mood is not in the map
# _DEFAULT_QUERY = "peaceful background ambient music"

# # YouTube Data API v3 search endpoint
# _YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


# async def handle_get_music_recommendation(mood: str) -> dict:
#     """
#     Search YouTube Data API for a track matching the given mood.

#     Args:
#         mood: mood string as detected by Gemini Live (e.g. "anxious", "happy")

#     Returns:
#         dict with keys:
#             - title: video title (Gemini reads this aloud)
#             - url:   full YouTube watch URL (frontend uses this for playback)
#             - error: present only if the API call fails
#     """
#     # Map mood to a curated search query, fall back to default if unknown
#     query = _MOOD_QUERY_MAP.get(mood.lower(), _DEFAULT_QUERY)

#     params = {
#         "part": "snippet",
#         "q": query,
#         "type": "video",
#         "maxResults": 1,           # We only need the top result
#         "videoCategoryId": "10",   # Category 10 = Music
#         "key": settings.YOUTUBE_API_KEY,
#     }

#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.get(_YT_SEARCH_URL, params=params, timeout=5.0)
#             response.raise_for_status()
#             data = response.json()

#             items = data.get("items", [])
#             if not items:
#                 return {"error": "No results found for this mood."}

#             video_id = items[0]["id"]["videoId"]
#             title = items[0]["snippet"]["title"]

#             return {
#                 "title": title,
#                 "url": f"https://www.youtube.com/watch?v={video_id}",
#             }

#         except httpx.HTTPError as e:
#             # Return error payload instead of raising — Gemini should handle
#             # gracefully rather than crashing the session
#             return {"error": f"YouTube API error: {str(e)}"}