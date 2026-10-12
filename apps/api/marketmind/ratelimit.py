"""A small in-memory sliding-window rate limiter.

Good enough for a single Render instance. With several instances this should move to
Redis (e.g. Upstash) so limits are shared.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            # Opportunistically drop idle keys so memory stays bounded.
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}
            return True
