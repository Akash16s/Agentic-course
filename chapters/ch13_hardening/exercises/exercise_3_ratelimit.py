"""EXERCISE 3 — Rate limiting yourself.

    pytest chapters/ch13_hardening/tests -q -k ratelimit
"""

from __future__ import annotations

import threading
import time
from typing import Callable


class RateLimiter:
    """Token bucket: `rate` permits per second, accumulating up to `capacity`.

    __init__(self, rate: float, *, capacity: float | None = None,
             clock=time.monotonic)
      * rate <= 0 -> ValueError
      * capacity defaults to `rate`
      * start FULL (self._tokens = capacity)

    A BUCKET, NOT A FIXED WINDOW. Real providers allow bursts; a strict "N per
    second" serialises work they would happily have taken all at once. The bucket
    lets you spend a burst and then settle to the sustained rate, which is what
    their limits actually model.
    """

    def __init__(self, rate: float, *, capacity: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        # TODO: implement
        raise NotImplementedError

    def _refill(self) -> None:
        """Add (now - last_update) * rate tokens, capped at capacity; update the
        timestamp. Call holding the lock.

        Refilling lazily on read rather than on a timer is the trick that makes
        this testable: with an injected clock there is no waiting anywhere.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def tokens(self) -> float:
        """Refill, then report."""
        # TODO: implement
        raise NotImplementedError

    def try_acquire(self, permits: float = 1.0) -> bool:
        """Take `permits` if available. Never blocks."""
        # TODO: implement
        raise NotImplementedError

    def time_until(self, permits: float = 1.0) -> float:
        """Seconds until `permits` are available; 0.0 if they are now.
        (permits - tokens) / rate."""
        # TODO: implement
        raise NotImplementedError

    def acquire(self, permits: float = 1.0, *,
                sleep: Callable[[float], None] = time.sleep) -> None:
        """Block until `permits` are taken.

        Loop: work out the wait, sleep at least a hair (`max(wait, 0.001)`) so a
        contended bucket cannot spin the CPU, and retry. `sleep` is injected, for
        the same reason it was in Chapter 1.
        """
        # TODO: implement
        raise NotImplementedError
