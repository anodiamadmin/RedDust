# services/track_verifier.py — YouTube Track Search & Verification Service
#
# Responsibility:
#   Given a search query string, find a publicly playable YouTube video and
#   return its metadata. This is NOT a simple search — it verifies that the
#   returned video is:
#     1. Public (not private or unlisted)
#     2. Embeddable (can be played in a third-party player)
#     3. Not region-restricted for India (IN)
#
# Why two API calls?
#   The YouTube search endpoint (v3/search) does NOT return video status or
#   region restriction info — only snippet data. We must make a second call to
#   the videos endpoint (v3/videos) with part=status,contentDetails to get
#   embeddability and region restriction. We fetch the top 3 search results,
#   then verify each one until we find a valid track.
#
# Caching:
#   Results are cached in-memory with a 1-hour TTL using cachetools.TTLCache.
#   This prevents burning YouTube API quota on repeated identical queries
#   within the same session or across concurrent sessions.
#   Cache is keyed on the normalized (lowercased, stripped) query string.
#
# Quota awareness:
#   YouTube Data API v3 free tier = 10,000 units/day.
#   - search call costs 100 units
#   - videos call costs 1 unit
#   Per recommendation: ~101 units. At 10k/day limit: ~99 recommendations/day.
#   Cache hits cost 0 units. Monitor usage in GCP console.
#
# Usage:
#   result = await verify_and_fetch_track("calming classical music for anxiety")
#   if result:
#       print(result["title"], result["track_url"])
#   else:
#       # No valid public track found — caller should skip or fallback
#       pass

import re
import logging
from typing import Optional

import httpx
from cachetools import TTLCache

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# YouTube Data API v3 endpoints
_YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# How many search results to fetch and attempt to verify
# We try up to 3 — if all fail verification, return None
_MAX_CANDIDATES = 3

# In-memory TTL cache: up to 256 unique queries, each cached for 1 hour
# Thread-safe enough for asyncio (single-threaded event loop)
_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)

# Regex to parse ISO 8601 duration (e.g. PT3M45S, PT1H2M3S, PT30S)
# YouTube returns duration in this format via contentDetails.duration
_ISO8601_DURATION_RE = re.compile(
    r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_iso8601_duration_ms(duration_str: str) -> Optional[int]:
    """
    Convert ISO 8601 duration string to milliseconds.

    Examples:
        "PT3M45S" -> 225000
        "PT1H2M3S" -> 3723000
        "PT30S" -> 30000
        "P0D" or "" -> None
    """
    match = _ISO8601_DURATION_RE.search(duration_str or "")
    if not match:
        return None

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
    return total_ms if total_ms > 0 else None


def _is_region_blocked(content_details: dict, region_code: str = "IN") -> bool:
    """
    Check if a video is region-restricted and blocks the given region.

    YouTube's regionRestriction has two modes:
      - allowed: only these regions can watch (if IN not in allowed → blocked)
      - blocked: these regions cannot watch (if IN in blocked → blocked)

    Returns True if the video is blocked in the given region.
    """
    restriction = content_details.get("regionRestriction", {})

    allowed = restriction.get("allowed")
    if allowed is not None:
        # Whitelist mode — IN must be in the allowed list
        return region_code not in allowed

    blocked = restriction.get("blocked")
    if blocked is not None:
        # Blacklist mode — IN must NOT be in the blocked list
        return region_code in blocked

    # No restriction info — assume playable
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def verify_and_fetch_track(query: str) -> Optional[dict]:
    """
    Search YouTube for a query and return the first verified playable track.

    Verification criteria:
      - privacyStatus == "public"
      - embeddable != False  (note: embeddable can be absent, treat as True)
      - Not region-blocked for IN

    Args:
        query: Natural language search string
               e.g. "calming classical music for anxiety relief"

    Returns:
        dict with keys:
            provider          : "youtube"
            provider_track_id : YouTube video ID (e.g. "dQw4w9WgXcQ")
            title             : Video title
            channel_title     : Channel/artist name
            thumbnail_url     : High-res thumbnail URL (or default if absent)
            duration_ms       : Duration in milliseconds (None if unavailable)
            track_url         : Full watch URL
        None if no valid public track is found.
    """
    # Normalize cache key
    cache_key = query.strip().lower()

    # Return cached result if available (saves quota)
    if cache_key in _cache:
        logger.debug("track_verifier: cache hit for query=%r", query)
        return _cache[cache_key]

    logger.info("track_verifier: searching YouTube for query=%r", query)

    region_code = settings.YOUTUBE_REGION_CODE
    language = settings.YOUTUBE_LANGUAGE

    async with httpx.AsyncClient(timeout=8.0) as client:

        # ------------------------------------------------------------------
        # Step 1: Search for candidate video IDs
        # ------------------------------------------------------------------
        try:
            search_resp = await client.get(
                _YT_SEARCH_URL,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "videoCategoryId": "10",        # Music category
                    "maxResults": _MAX_CANDIDATES,
                    "regionCode": region_code,
                    "relevanceLanguage": language,
                    "key": settings.YOUTUBE_API_KEY,
                },
            )
            search_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Handle quota exhaustion gracefully — log and return None
            if e.response.status_code == 403:
                logger.error(
                    "track_verifier: YouTube API quota exceeded or forbidden. "
                    "Check GCP console. query=%r", query
                )
            else:
                logger.error(
                    "track_verifier: search HTTP error %d for query=%r",
                    e.response.status_code, query
                )
            return None
        except httpx.RequestError as e:
            logger.error("track_verifier: network error during search: %s", e)
            return None

        search_data = search_resp.json()
        items = search_data.get("items", [])

        if not items:
            logger.warning("track_verifier: no search results for query=%r", query)
            _cache[cache_key] = None
            return None

        # Extract candidate video IDs and their snippet data
        # snippet is already available from search — no need to re-fetch it
        candidates = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                candidates.append({
                    "video_id": video_id,
                    "title": item["snippet"].get("title", "Unknown Title"),
                    "channel_title": item["snippet"].get("channelTitle", "Unknown"),
                    "thumbnail_url": (
                        item["snippet"]
                        .get("thumbnails", {})
                        .get("high", {})
                        .get("url")
                        or item["snippet"]
                        .get("thumbnails", {})
                        .get("default", {})
                        .get("url", "")
                    ),
                })

        if not candidates:
            logger.warning("track_verifier: no valid video IDs in search results for query=%r", query)
            _cache[cache_key] = None
            return None

        # ------------------------------------------------------------------
        # Step 2: Verify candidates via videos endpoint (status + contentDetails)
        # ------------------------------------------------------------------
        video_ids_str = ",".join(c["video_id"] for c in candidates)

        try:
            videos_resp = await client.get(
                _YT_VIDEOS_URL,
                params={
                    "part": "status,contentDetails",
                    "id": video_ids_str,
                    "key": settings.YOUTUBE_API_KEY,
                },
            )
            videos_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.error("track_verifier: YouTube API quota exceeded during verification.")
            else:
                logger.error(
                    "track_verifier: videos HTTP error %d",
                    e.response.status_code
                )
            return None
        except httpx.RequestError as e:
            logger.error("track_verifier: network error during verification: %s", e)
            return None

        # Build a lookup map: video_id -> {status, contentDetails}
        video_details: dict[str, dict] = {}
        for v in videos_resp.json().get("items", []):
            video_details[v["id"]] = {
                "status": v.get("status", {}),
                "contentDetails": v.get("contentDetails", {}),
            }

        # ------------------------------------------------------------------
        # Step 3: Pick the first candidate that passes all checks
        # ------------------------------------------------------------------
        for candidate in candidates:
            vid = candidate["video_id"]
            details = video_details.get(vid)

            if details is None:
                # Video details not returned — likely deleted or restricted
                logger.debug("track_verifier: no details for video_id=%s, skipping", vid)
                continue

            status = details["status"]
            content_details = details["contentDetails"]

            # Must be public
            if status.get("privacyStatus") != "public":
                logger.debug(
                    "track_verifier: video_id=%s is not public (status=%s), skipping",
                    vid, status.get("privacyStatus")
                )
                continue

            # Must be embeddable (absent = True by default)
            if status.get("embeddable") is False:
                logger.debug("track_verifier: video_id=%s is not embeddable, skipping", vid)
                continue

            # Must not be region-blocked for IN
            if _is_region_blocked(content_details, region_code):
                logger.debug(
                    "track_verifier: video_id=%s is region-blocked for %s, skipping",
                    vid, region_code
                )
                continue

            # All checks passed — build result
            result = {
                "provider": "youtube",
                "provider_track_id": vid,
                "title": candidate["title"],
                "channel_title": candidate["channel_title"],
                "thumbnail_url": candidate["thumbnail_url"],
                "duration_ms": _parse_iso8601_duration_ms(
                    content_details.get("duration", "")
                ),
                "track_url": f"https://www.youtube.com/watch?v={vid}",
            }

            logger.info(
                "track_verifier: verified track video_id=%s title=%r for query=%r",
                vid, result["title"], query
            )

            # Cache the successful result
            _cache[cache_key] = result
            return result

        # No candidate passed verification
        logger.warning(
            "track_verifier: all %d candidates failed verification for query=%r",
            len(candidates), query
        )
        _cache[cache_key] = None
        return None
