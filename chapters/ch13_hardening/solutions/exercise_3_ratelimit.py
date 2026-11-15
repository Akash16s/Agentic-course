"""SOLUTION — Chapter 13, Exercise 3."""

from __future__ import annotations

import threading
import time
from typing import Callable


class RateLimiter:
    """Token bucket: `rate` permits per second, bursting up to `capacity`.

    A bucket rather than a fixed window because real limits allow bursts. A strict
    "N per second" limiter serialises work that the provider would happily have
    taken all at once.
    """

    def __init__(self, rate: float, *, capacity: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self.clock = clock
        self._tokens = float(self.capacity)
        self._updated = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self.clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
        self._updated = now

    @property
    def tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

    def try_acquire(self, permits: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= permits:
                self._tokens -= permits
                return True
            return False

    def time_until(self, permits: float = 1.0) -> float:
        """Seconds until `permits` are available. 0.0 if they are available now."""
        with self._lock:
            self._refill()
            if self._tokens >= permits:
                return 0.0
            return (permits - self._tokens) / self.rate

    def acquire(self, permits: float = 1.0, *,
                sleep: Callable[[float], None] = time.sleep) -> None:
        """Block until permits are available. `sleep` is injected for tests."""
        while True:
            wait = self.time_until(permits)
            if wait <= 0 and self.try_acquire(permits):
                return
            sleep(max(wait, 0.001))
