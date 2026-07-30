from collections import defaultdict
from typing import List, Dict

# {session_id: [{"role": "user"|"model", "text": str}]}
_store: Dict[str, List[Dict[str, str]]] = defaultdict(list)


def get_history(session_id: str) -> List[Dict[str, str]]:
    return _store[session_id]


def append_message(session_id: str, role: str, text: str) -> None:
    _store[session_id].append({"role": role, "text": text})


def clear_session(session_id: str) -> None:
    _store.pop(session_id, None)
