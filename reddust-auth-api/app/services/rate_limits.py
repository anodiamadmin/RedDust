"""Single-process local-development rate limiter; NOT a production substitute."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException, Request

_lock = Lock()
_events: dict[str, deque[float]] = defaultdict(deque)


def enforce_local_rate_limit(request: Request, *, category: str, limit: int = 10, seconds: int = 60) -> None:
    # Do not trust caller-supplied X-Forwarded-For. Proxy policy is separate.
    remote = request.client.host if request.client else "unknown"
    key = f"{category}:{remote}"
    now = monotonic()
    with _lock:
        entries = _events[key]
        while entries and entries[0] <= now - seconds:
            entries.popleft()
        if len(entries) >= limit:
            raise HTTPException(429, detail={"code": "RATE_LIMITED", "message": "Too many requests"})
        entries.append(now)