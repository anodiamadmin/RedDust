r"""
scripts/test_music_recommender.py — Manual test for music_recommender.py

Run from backend/ (Windows PowerShell, venv_windows):
    cd D:\Anodiam\2026\RedDust_Parent\RedDust\backend
    venv_windows\Scripts\Activate.ps1
    pip install google-genai asyncpg pydantic-settings python-dotenv
    python -m scripts.test_music_recommender

What this tests:
    1. build_music_recommendation_context() runs without error (new user = empty context)
    2. recommend_tracks() falls back gracefully when context is empty
    3. recommend_tracks() calls Gemini and returns valid query dicts when context exists

Expected output (success):
    [1] Context built for new user (no history): OK
    [2] Fallback queries returned for empty context: OK
        query: peaceful background ambient music
    [3] Gemini recommendation with mock context: OK
        query: <some specific query>
        outcome: <desired outcome>
        rationale: <rationale>
    [4] ALL TESTS PASSED

Possible errors:
    - google.api_core errors → check GEMINI_API_KEY in .env
    - asyncpg errors → check SUPABASE_DB_URL in .env
    - json.JSONDecodeError → Gemini returned non-JSON (unlikely with response_mime_type set)
"""

import asyncio
import sys
import os
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.pool import create_pool
from app.services.music_recommender import (
    build_music_recommendation_context,
    recommend_tracks,
)


async def main():
    # -----------------------------------------------------------------------
    # [1] Test context build for a non-existent user (empty context expected)
    # -----------------------------------------------------------------------
    pool = await create_pool()
    fake_user_id = uuid4()
    fake_session_id = uuid4()

    context = await build_music_recommendation_context(fake_user_id, fake_session_id, pool)

    assert isinstance(context, dict), "Context must be a dict"
    assert "preferences" in context
    assert "soul_scores" in context
    assert "recent_tracks" in context
    assert context["preferences"] == [], "New user should have no preferences"

    print("[1] Context built for new user (no history): OK")

    # -----------------------------------------------------------------------
    # [2] Test fallback — empty context should return hardcoded query
    # -----------------------------------------------------------------------
    results = await recommend_tracks(fake_user_id, fake_session_id, "anxious", context)

    assert isinstance(results, list), "Results must be a list"
    assert len(results) >= 1, "Must return at least 1 query"
    assert "query_string" in results[0], "Each result must have query_string"

    print(f"[2] Fallback queries returned for empty context: OK")
    print(f"    query: {results[0]['query_string']}")

    # -----------------------------------------------------------------------
    # [3] Test Gemini call with a mock context (simulates a returning user)
    # -----------------------------------------------------------------------
    mock_context = {
        "preferences": [
            {"preference_type": "genre",  "preference_value": "Bollywood", "confidence": 0.95, "source": "per_turn"},
            {"preference_type": "decade", "preference_value": "1990s",     "confidence": 0.80, "source": "session_batch"},
            {"preference_type": "artist", "preference_value": "AR Rahman", "confidence": 0.90, "source": "per_turn"},
        ],
        "soul_scores": [
            {"dimension_name": "Calmness",    "final_score": 35.0, "duration_code": "Short–Medium"},
            {"dimension_name": "Energy",      "final_score": 60.0, "duration_code": "Short"},
            {"dimension_name": "Motivation",  "final_score": 55.0, "duration_code": "Short–Medium"},
        ],
        "recent_tracks": [
            {"title": "Kal Ho Naa Ho", "provider_track_id": "abc123", "rating": 5, "skipped": False, "completed": True},
            {"title": "Generic Ambient Music", "provider_track_id": "xyz789", "rating": 2, "skipped": True, "completed": False},
        ],
    }

    gemini_results = await recommend_tracks(fake_user_id, fake_session_id, "anxious", mock_context)

    assert isinstance(gemini_results, list)
    assert len(gemini_results) >= 1
    assert "query_string" in gemini_results[0]

    print(f"[3] Gemini recommendation with mock context: OK")
    for r in gemini_results:
        print(f"    query:     {r['query_string']}")
        print(f"    outcome:   {r['desired_outcome']}")
        print(f"    rationale: {r['rationale']}")
        print()

    await pool.close()
    print("[4] ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
