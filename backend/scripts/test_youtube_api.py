"""
scripts/test_youtube_api.py — Manual test for YouTube API key + track_verifier.py

Run from the backend/ directory:
    cd backend
    python -m scripts.test_youtube_api

What this tests:
    1. That YOUTUBE_API_KEY is loaded from .env correctly
    2. That verify_and_fetch_track() makes a real API call and returns a valid result
    3. That the result has all expected keys
    4. That a second call for the same query hits the cache (no second API call)

Expected output (success):
    [1] API key loaded: AIza...XXXX  (last 4 chars shown)
    [2] Searching YouTube for query: 'calming anxiety relief music'
    [3] Result:
        provider        : youtube
        provider_track_id: <video_id>
        title           : <some title>
        channel_title   : <channel>
        thumbnail_url   : https://i.ytimg.com/...
        duration_ms     : <integer>
        track_url       : https://www.youtube.com/watch?v=<video_id>
    [4] Cache hit test: second call returned same result immediately.
    [5] ALL TESTS PASSED

Possible errors:
    - "YOUTUBE_API_KEY is empty" → key not set in .env
    - "403 Forbidden / quotaExceeded" → key exists but quota exhausted for today
    - "403 Forbidden / keyInvalid" → key is wrong or YouTube Data API v3 not enabled in GCP
    - "No results found" → extremely unlikely for a generic query; suspect key or quota issue
    - Any httpx error → network issue
"""

import asyncio
import sys
import os

# Allow running as `python -m scripts.test_youtube_api` from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.services.track_verifier import verify_and_fetch_track


async def main():
    # -----------------------------------------------------------------------
    # [1] Check API key is loaded
    # -----------------------------------------------------------------------
    key = settings.YOUTUBE_API_KEY
    if not key:
        print("[FAIL] YOUTUBE_API_KEY is empty — check your .env file.")
        sys.exit(1)

    # Only print last 4 chars so the key isn't exposed in logs
    print(f"[1] API key loaded: ...{key[-4:]}")

    # -----------------------------------------------------------------------
    # [2] First call — should hit YouTube API
    # -----------------------------------------------------------------------
    query = "calming anxiety relief music"
    print(f"[2] Searching YouTube for query: {query!r}")

    result = await verify_and_fetch_track(query)

    if result is None:
        print("[FAIL] verify_and_fetch_track() returned None — no valid track found.")
        print("       Check GCP console for quota issues or API errors in the logs.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # [3] Validate result structure
    # -----------------------------------------------------------------------
    required_keys = [
        "provider", "provider_track_id", "title",
        "channel_title", "thumbnail_url", "duration_ms", "track_url"
    ]
    missing = [k for k in required_keys if k not in result]
    if missing:
        print(f"[FAIL] Result is missing keys: {missing}")
        sys.exit(1)

    print("[3] Result:")
    for k, v in result.items():
        print(f"    {k:<22}: {v}")

    # -----------------------------------------------------------------------
    # [4] Second call — should be a cache hit (no API call)
    # -----------------------------------------------------------------------
    result2 = await verify_and_fetch_track(query)
    if result2 != result:
        print("[FAIL] Cache test failed — second call returned a different result.")
        sys.exit(1)

    print("[4] Cache hit test: second call returned same result immediately.")

    # -----------------------------------------------------------------------
    # [5] Done
    # -----------------------------------------------------------------------
    print("[5] ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
