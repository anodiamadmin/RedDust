# services/session_store.py — In-memory conversation session store
#
# Stores the message history for each active session as a list of {role, text} dicts.
# This history is passed to Gemini on every request so the LLM has full conversation context.
#
# ⚠️ IMPORTANT LIMITATION — Production Concern:
# This store lives in Python process memory. This means:
#   1. All sessions are LOST if the server restarts.
#   2. If multiple server instances run (horizontal scaling), each has its own isolated store.
#      A user mid-conversation routed to a different instance will lose their history.
# Production fix: Replace this with a shared Redis store with TTL-based session expiry.

from collections import defaultdict
from typing import List, Dict

# Structure: { session_id (str) -> [ {"role": "user"|"model", "text": str}, ... ] }
# defaultdict(list) means accessing a non-existent key auto-creates an empty list — no KeyError
_store: Dict[str, List[Dict[str, str]]] = defaultdict(list)


def get_history(session_id: str) -> List[Dict[str, str]]:
    """Returns the full message history for a session. Returns [] for new sessions."""
    return _store[session_id]


def append_message(session_id: str, role: str, text: str) -> None:
    """Appends a single message turn to the session history.
    role must be 'user' or 'model' — these are Gemini's expected role labels."""
    _store[session_id].append({"role": role, "text": text})


def clear_session(session_id: str) -> None:
    """Deletes a session and its entire history. Useful for logout or reset flows."""
    _store.pop(session_id, None)  # pop with default=None avoids KeyError if session doesn't exist
