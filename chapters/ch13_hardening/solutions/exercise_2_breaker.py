"""SOLUTION — Chapter 13, Exercise 2."""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Callable

from agentlib import errors


class BreakerState(str, Enum):
    CLOSED = "closed"        # normal: requests flow
    OPEN = "open"            # failing: reject immediately
    HALF_OPEN = "half_open"  # probing: let one through and see


class CircuitOpen(errors.LLMError):
    """The breaker rejected this call without trying."""

    retryable = False


class CircuitBreaker:
    """Stop hammering a service that is already down.

    Without one, a provider outage turns into: every request waits for a timeout,
    your workers all block, your queue backs up, and you take yourself down
    alongside them. The breaker converts a slow cascading failure into a fast,
    obvious one.

        CLOSED --(failure_threshold consecutive failures)--> OPEN
        OPEN   --(reset_timeout_s elapses)-----------------> HALF_OPEN
        HALF_OPEN --(success_threshold successes)----------> CLOSED
        HALF_OPEN --(any failure)--------------------------> OPEN
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        success_threshold: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self.success_threshold = success_threshold
        self.clock = clock
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> BreakerState:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _maybe_half_open(self) -> None:
        if (self._state is BreakerState.OPEN
                and self.clock() - self._opened_at >= self.reset_timeout_s):
            self._state = BreakerState.HALF_OPEN
            self._successes = 0

    def allow(self) -> bool:
        return self.state is not BreakerState.OPEN

    def record_success(self) -> None:
        with self._lock:
            if self._state is BreakerState.HALF_OPEN:
                self._successes += 1
                if self._successes >= self.success_threshold:
                    self._state = BreakerState.CLOSED
                    self._failures = 0
            else:
                self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            if self._state is BreakerState.HALF_OPEN:
                # the probe failed: straight back to OPEN, full timeout again
                self._state = BreakerState.OPEN
                self._opened_at = self.clock()
                self._failures = self.failure_threshold
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = BreakerState.OPEN
                self._opened_at = self.clock()

    def call(self, fn: Callable[[], Any]) -> Any:
        """Run `fn` through the breaker."""
        if not self.allow():
            raise CircuitOpen(
                f"circuit open; retry in "
                f"{self.reset_timeout_s - (self.clock() - self._opened_at):.0f}s"
            )
        try:
            result = fn()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
