"""Token bucket rate limiter dengan exponential backoff."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Thread-safe token bucket."""

    def __init__(self, rate_per_minute: float = 30.0) -> None:
        self.rate_per_second = rate_per_minute / 60.0
        self._tokens = rate_per_minute  # mulai penuh
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens += elapsed * self.rate_per_second
        cap = self.rate_per_second * 60  # max = 1 menit
        if self._tokens > cap:
            self._tokens = cap
        self._last_refill = now

    def acquire(self) -> None:
        """Block sampai dapat 1 token."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self.rate_per_second
            time.sleep(wait)


def backoff_sleep(
    attempt: int,
    base: float = 2.0,
    max_wait: float = 120.0,
    jitter: float = 0.5,
) -> float:
    """Tidur eksponensial, return detik yang ditunggu."""
    import random
    wait = min(base ** attempt + random.uniform(0, jitter), max_wait)
    time.sleep(wait)
    return wait
