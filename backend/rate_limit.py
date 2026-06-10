"""
rate_limit.py — minimal in-process sliding-window rate limiter.

Used to cap calls to the expensive LLM chat endpoint per user. State lives in
memory, so the limit is enforced *per process*: behind multiple workers or
replicas each instance keeps its own window. That is acceptable for the current
single-instance deployment; a multi-instance setup should swap this for a shared
store (Redis) behind the same `allow()` interface.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """
        Record an attempt for `key`. Returns (allowed, retry_after_seconds).
        When blocked, retry_after is the seconds until the window frees a slot.
        """
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds

        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                retry_after = max(1, int(hits[0] + self.window_seconds - now))
                return False, retry_after

            hits.append(now)
            return True, 0
