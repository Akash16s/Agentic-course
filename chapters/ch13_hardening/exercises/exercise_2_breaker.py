"""EXERCISE 2 — The circuit breaker.

    pytest chapters/ch13_hardening/tests -q -k breaker
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Callable

from agentlib import errors


class BreakerState(str, Enum):
    """CLOSED (normal), OPEN (reject fast), HALF_OPEN (probing)."""

    CLOSED = "closed"
    # TODO: add OPEN and HALF_OPEN


class CircuitOpen(errors.LLMError):
    """Rejected without trying. NOT retryable — that is the whole point."""

    retryable = False


class CircuitBreaker:
    """Stop hammering a service that is already down.

        CLOSED    --(failure_threshold CONSECUTIVE failures)--> OPEN
        OPEN      --(reset_timeout_s elapses)----------------->  HALF_OPEN
        HALF_OPEN --(success_threshold successes)------------->  CLOSED
        HALF_OPEN --(any failure)----------------------------->  OPEN (full timeout)

    __init__(self, *, failure_threshold=5, reset_timeout_s=30.0,
             success_threshold=2, clock=time.monotonic)
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        success_threshold: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Also keep: _state (CLOSED), _failures, _successes, _opened_at, a Lock."""
        # TODO: implement
        raise NotImplementedError

    @property
    def state(self) -> BreakerState:
        """The current state, AFTER checking whether an OPEN breaker should have
        moved to HALF_OPEN. Reading the state is what advances the timeout —
        there is no background timer to do it for you.
        """
        # TODO: implement
        raise NotImplementedError

    def _maybe_half_open(self) -> None:
        """OPEN and the reset timeout has elapsed -> HALF_OPEN, reset _successes.
        Call this holding the lock."""
        # TODO: implement
        raise NotImplementedError

    def allow(self) -> bool:
        """True unless the state is OPEN."""
        # TODO: implement
        raise NotImplementedError

    def record_success(self) -> None:
        """HALF_OPEN -> count successes; at success_threshold, close and reset.
        CLOSED      -> reset the failure count to 0.

        RESETTING ON SUCCESS IS THE POINT. You want CONSECUTIVE failures. A
        lifetime tally means a perfectly healthy service trips the breaker a month
        after launch, for no reason anyone can find.
        """
        # TODO: implement
        raise NotImplementedError

    def record_failure(self) -> None:
        """HALF_OPEN -> straight back to OPEN, reset _opened_at, and set _failures
                       to failure_threshold. Half a recovery is not a recovery: the
                       probe failing must cost the FULL timeout again, not one more
                       failure's worth.
           otherwise -> increment; at failure_threshold, OPEN and stamp _opened_at.
        """
        # TODO: implement
        raise NotImplementedError

    def call(self, fn: Callable[[], Any]) -> Any:
        """Run `fn` through the breaker.

        * not allowed -> raise CircuitOpen with a message saying how long is left
        * fn raises   -> record_failure(), then RE-RAISE the original exception
        * success     -> record_success(), return the result
        """
        # TODO: implement
        raise NotImplementedError
