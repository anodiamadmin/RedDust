"""
session_store.py — In-memory HTTP chat session history store.

Stores the last N messages per session_id for the /chat HTTP endpoint.
Uses TTLCache to cap memory usage: max 1000 concurrent sessions,
each session expires after 2 hours of inactivity.

Note: This is separate from Gemini Live audio sessions (WebSocket).
"""

import logging
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Max 1000 concurrent sessions; each expires after 2 hours of inactivity.
# TTLCache raises KeyError on missing keys (unlike defaultdict) — handle explicitly.
_store: TTLCache = TTLCache(maxsize=1000, ttl=7200)


def get_history(session_id: str) -> list[dict[str, Any]]:
    """Return message history for the given session. Returns [] if not found or expired."""
    try:
        return _store[session_id]
    except KeyError:
        return []


def append_message(session_id: str, message: dict[str, Any]) -> None:
    """Append a message to the session history. Creates the session if it doesn't exist."""
    if session_id not in _store:
        _store[session_id] = []
    _store[session_id].append(message)


def clear_session(session_id: str) -> None:
    """Delete a session from the store."""
    try:
        del _store[session_id]
    except KeyError:
        logger.debug("clear_session called on unknown session_id: %s", session_id)