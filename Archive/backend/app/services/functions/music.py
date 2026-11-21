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
#
# Schema notes (music_track):
#   - PK is track_id (UUID), not id
#   - No artist/thumbnail_url columns — stored in metadata_json JSONB
#   - duration_ms is a direct column
#   - UNIQUE constraint on (provider, provider_track_id)
#
# Schema notes (music_recommendation):
#   - FK to music_track is track_id (not music_track_id)
#   - Rank column is recommendation_rank (not rank)
#   - user_id is required (NOT NULL)
#   - recommendation_context is JSONB (must pass dict, not string)

import asyncio
import json
import logging
from uuid import UUID

import asyncpg

from app.services.music_recommender import build_music_recommendation_context, recommend_tracks
from app.services.track_verifier import verify_and_fetch_track

logger = logging.getLogger(__name__)


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
        args:            function call args from Gemini Live. Expected keys:
                           - mood_hint     (required) : current emotional state
                           - desired_mood  (optional) : target emotional state
                           - activity      (optional) : what the user is doing
                           - energy_level  (optional) : low | medium | high
                           - time_of_day   (optional) : morning | afternoon | evening | night
                           - session_goal  (optional) : what the user wants to achieve this session
        user_id:         current user
        session_id:      current session
        conversation_id: current conversation
        turn_id:         current turn number (maps to conversation_turn.turn_id)
        pool:            asyncpg connection pool

    Returns:
        dict with key 'tracks': list of recommended track dicts, or 'error' on failure.
        Gemini Live reads track titles aloud; frontend handles playback via url.
    """
    # Extract all signals Gemini may have passed — only mood_hint is required
    mood_hint    = args.get("mood_hint", "neutral")
    desired_mood = args.get("desired_mood")   # where the user wants to go emotionally
    activity     = args.get("activity")       # study, sleep, workout, relax, etc.
    energy_level = args.get("energy_level")   # low | medium | high
    time_of_day  = args.get("time_of_day")    # morning | afternoon | evening | night
    session_goal = args.get("session_goal")   # e.g. "focus for 3 hours", "wind down before sleep"

    try:
        # Step 1: build user context (preferences + soul score + recent reactions)
        context = await build_music_recommendation_context(user_id, session_id, pool)

        # Step 2: Gemini Flash generates personalised query strings
        # All six signals passed so the prompt can use whichever are available
        recommendations = await recommend_tracks(
            user_id=user_id,
            session_id=session_id,
            current_mood_hint=mood_hint,
            desired_mood=desired_mood,
            activity=activity,
            energy_level=energy_level,
            time_of_day=time_of_day,
            session_goal=session_goal,
            context=context,
        )

        if not recommendations:
            return {"error": "Could not generate music recommendations."}

        # Step 3: verify each query string against YouTube API concurrently
        verify_tasks = [
            verify_and_fetch_track(rec["query_string"])
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
                    logger.warning(
                        "Track verification failed for query: %s", rec.get("query_string")
                    )
                    continue

                # ----------------------------------------------------------
                # Upsert into music_track
                # Schema: PK=track_id, no artist/thumbnail columns —
                # those go into metadata_json JSONB. duration_ms is a column.
                # UNIQUE on (provider, provider_track_id).
                # ----------------------------------------------------------
                track_metadata = {
                    "channel_title":  track.get("channel_title"),
                    "thumbnail_url":  track.get("thumbnail_url"),
                }

                track_id = await conn.fetchval(
                    """
                    INSERT INTO reddust.music_track
                        (provider, provider_track_id, title, duration_ms,
                         track_url, metadata_json)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (provider, provider_track_id)
                    DO UPDATE SET
                        title         = EXCLUDED.title,
                        duration_ms   = EXCLUDED.duration_ms,
                        track_url     = EXCLUDED.track_url,
                        metadata_json = EXCLUDED.metadata_json
                    RETURNING track_id
                    """,
                    track["provider"],
                    track["provider_track_id"],
                    track["title"],
                    track.get("duration_ms"),
                    track["track_url"],
                    json.dumps(track_metadata),   # JSONB — must be serialised string
                )

                # ----------------------------------------------------------
                # Insert music_recommendation row
                # Schema: FK=track_id, rank=recommendation_rank, user_id required,
                # recommendation_context is JSONB (pass dict serialised as string)
                # ----------------------------------------------------------
                recommendation_context = {
                    "mood_hint":    mood_hint,
                    "desired_mood": desired_mood,
                    "activity":     activity,
                    "energy_level": energy_level,
                    "time_of_day":  time_of_day,
                    "session_goal": session_goal,
                    "query_string": rec.get("query_string"),
                    "desired_outcome": rec.get("desired_outcome"),
                }

                await conn.execute(
                    """
                    INSERT INTO reddust.music_recommendation
                        (user_id, session_id, conversation_id, turn_id,
                         track_id, recommendation_rank, rationale,
                         recommendation_context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    user_id,
                    session_id,
                    conversation_id,
                    turn_id,
                    track_id,
                    rank,
                    rec.get("rationale"),
                    json.dumps(recommendation_context),  # JSONB — must be serialised
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
