from __future__ import annotations

import time
from collections import deque
from threading import Lock

from app.llm.exceptions import LLMRateLimitError


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter enforcing requests per minute."""

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0):
        self.rpm = max(1, requests_per_minute)
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def acquire(self, timeout_s: float = 5.0) -> None:
        """Acquire a slot or raise LLMRateLimitError if rate limit is exhausted within timeout."""
        start_wait = time.monotonic()
        while True:
            with self._lock:
                now = time.monotonic()
                # Prune timestamps outside the current sliding window
                while self._timestamps and self._timestamps[0] <= now - self.window_seconds:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.rpm:
                    self._timestamps.append(now)
                    return

            if time.monotonic() - start_wait > timeout_s:
                raise LLMRateLimitError(
                    f"Local rate limiter exceeded threshold of {self.rpm} requests per minute."
                )
            time.sleep(0.05)

    def reset(self) -> None:
        with self._lock:
            self._timestamps.clear()
