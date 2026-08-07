# services/functions/music.py — Music recommendation function handler
#
# Responsibility: given a mood string from Gemini Live, search YouTube Data API
# for a relevant track and return the top result's title + URL.
#
# Why YouTube Data API?
#   - Free tier (10,000 units/day) is sufficient for a wellness app
#   - No licensing issues — we return a URL, not the audio itself
#   - Wide catalogue covering ambient, classical, nature sounds, etc.
#
# How this fits into the session:
#   - Gemini Live calls get_music_recommendation(mood="anxious")
#   - function_dispatcher routes here
#   - We query YouTube, return {title, url}
#   - Gemini reads the title aloud and the frontend handles playback via the URL
#
# Mood → search query mapping:
#   - We don't pass the raw mood directly to YouTube (e.g. "anxious" returns
#     unpredictable results). Instead we map moods to curated search terms that
#     reliably surface calming/appropriate content.

import httpx
from app.config import settings

# Curated search terms per mood — tuned for wellness/ambient content
# Add more moods here as the product evolves
_MOOD_QUERY_MAP = {
    "anxious":   "calming anxiety relief music",
    "sad":       "gentle uplifting music for sadness",
    "happy":     "upbeat positive background music",
    "stressed":  "stress relief meditation music",
    "tired":     "relaxing sleep music ambient",
    "angry":     "calming music for anger relief",
    "neutral":   "peaceful background ambient music",
    "motivated": "motivational focus music",
}

# Fallback search term if mood is not in the map
_DEFAULT_QUERY = "peaceful background ambient music"

# YouTube Data API v3 search endpoint
_YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


async def handle_get_music_recommendation(mood: str) -> dict:
    """
    Search YouTube Data API for a track matching the given mood.

    Args:
        mood: mood string as detected by Gemini Live (e.g. "anxious", "happy")

    Returns:
        dict with keys:
            - title: video title (Gemini reads this aloud)
            - url:   full YouTube watch URL (frontend uses this for playback)
            - error: present only if the API call fails
    """
    # Map mood to a curated search query, fall back to default if unknown
    query = _MOOD_QUERY_MAP.get(mood.lower(), _DEFAULT_QUERY)

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,           # We only need the top result
        "videoCategoryId": "10",   # Category 10 = Music
        "key": settings.YOUTUBE_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(_YT_SEARCH_URL, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if not items:
                return {"error": "No results found for this mood."}

            video_id = items[0]["id"]["videoId"]
            title = items[0]["snippet"]["title"]

            return {
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }

        except httpx.HTTPError as e:
            # Return error payload instead of raising — Gemini should handle
            # gracefully rather than crashing the session
            return {"error": f"YouTube API error: {str(e)}"}