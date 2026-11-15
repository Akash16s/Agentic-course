"""SOLUTION — Chapter 13, Exercise 4."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from agentlib import errors
from agentlib.llm import Message


class BudgetGuard:
    """A PRE-FLIGHT spend limit, unlike Chapter 1's after-the-fact CostTracker.

    Chapter 1 raises on the call that crosses the line — the money is already gone.
    This refuses the call before it happens, using an estimate. Both are useful:
    the estimate can be wrong, so you want the real accounting too.
    """

    def __init__(self, budget_usd: float,
                 *, estimate: Callable[[list[Message]], float] | None = None) -> None:
        self.budget_usd = budget_usd
        self.spent = 0.0
        self.estimate = estimate
        self._lock = threading.Lock()

    @property
    def remaining(self) -> float:
        return self.budget_usd - self.spent

    def check(self, messages: list[Message] | None = None) -> None:
        """Raise BudgetExceeded if this call would (probably) go over."""
        with self._lock:
            projected = self.spent
            if messages is not None and self.estimate is not None:
                projected += self.estimate(messages)
            if projected > self.budget_usd:
                raise errors.BudgetExceeded(projected, self.budget_usd)

    def record(self, cost: float) -> None:
        with self._lock:
            self.spent += cost


# ---------------------------------------------------------------- idempotency


class IdempotencyStore:
    """Remember the result of an operation by key, so a retry does not repeat it.

    The problem this solves: a client times out, retries, and your agent sends the
    refund twice. The network cannot tell you whether the first attempt succeeded;
    only a key you control can.

    In production this is Redis or a database table with a unique constraint, not a
    dict. The interface is the same.
    """

    def __init__(self, *, ttl_s: float = 86_400,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl_s = ttl_s
        self.clock = clock
        self._entries: dict[str, tuple[float, Any]] = {}
        self._in_flight: set[str] = set()
        self._lock = threading.Lock()

    def run(self, key: str, fn: Callable[[], Any]) -> Any:
        """Run `fn` once per key. Later calls return the stored result."""
        with self._lock:
            stored = self._entries.get(key)
            if stored is not None and self.clock() - stored[0] <= self.ttl_s:
                return stored[1]
            if key in self._in_flight:
                raise errors.LLMError(f"operation {key!r} is already in flight")
            self._in_flight.add(key)

        try:
            result = fn()
        finally:
            with self._lock:
                self._in_flight.discard(key)

        with self._lock:
            self._entries[key] = (self.clock(), result)
        return result

    def seen(self, key: str) -> bool:
        with self._lock:
            stored = self._entries.get(key)
            return stored is not None and self.clock() - stored[0] <= self.ttl_s


# ------------------------------------------------------- prompt cache markers


def mark_cacheable_prefix(messages: list[Message], *, upto: int = 1) -> list[Message]:
    """Add Anthropic-style `cache_control` to the first `upto` messages.

    Provider prompt caching stores the unchanged PREFIX of your request so
    re-sending it is far cheaper and faster. It only helps if the prefix really is
    unchanged — put the system prompt and tool definitions first and never rewrite
    them mid-conversation. A timestamp in the system prompt busts the cache on
    every single call, which is a remarkably common and expensive mistake.

    Through OpenRouter, support and syntax vary by underlying model. Treat this as
    best-effort and measure whether it actually helped.
    """
    out: list[Message] = []
    for index, message in enumerate(messages):
        if index < upto:
            copy = dict(message)
            copy["cache_control"] = {"type": "ephemeral"}
            out.append(copy)
        else:
            out.append(message)
    return out
