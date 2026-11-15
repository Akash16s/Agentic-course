"""Production hardening — the things that stop a working agent from falling over.

Promoted from Chapter 13.

Chapter 1 gave you retries. This is the rest: caching, circuit breaking, rate
limiting, pre-flight budget guards and idempotency. None of it is clever. All of it
is the difference between a demo and a service.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from agentlib import errors
from agentlib.llm import LLMResponse, Message

# --------------------------------------------------------------------- cache


def cache_key(messages: list[Message], **params: Any) -> str:
    """A stable hash of everything that affects the answer.

    Everything: the messages AND the parameters. Two requests with the same
    messages but different temperature or different tools are different requests,
    and a cache keyed on messages alone will serve you the wrong one — silently,
    and only sometimes, which is the worst kind of bug.

    `sort_keys=True` because dict ordering must not change the key.
    """
    payload = {
        "messages": messages,
        "params": {k: v for k, v in sorted(params.items()) if v is not None},
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


@dataclass
class CacheEntry:
    value: Any
    stored_at: float
    hits: int = 0


class ResponseCache:
    """An LRU cache with a TTL, keyed on the full request.

    Worth having for three separate reasons:
      * eval suites re-run identical requests constantly (Chapter 10)
      * retries after a downstream failure re-send the same request
      * agents genuinely re-ask the same sub-question

    Only ever cache DETERMINISTIC requests. At temperature > 0 the caller asked for
    variation, and handing back a cached answer quietly takes it away.
    """

    def __init__(self, *, max_size: int = 1_000, ttl_s: float | None = 3_600,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_size = max_size
        self.ttl_s = ttl_s
        self.clock = clock
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            if self.ttl_s is not None and self.clock() - entry.stored_at > self.ttl_s:
                del self._entries[key]
                self.misses += 1
                return None
            self._entries.move_to_end(key)   # LRU: touching makes it recent
            entry.hits += 1
            self.hits += 1
            return entry.value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._entries[key] = CacheEntry(value=value, stored_at=self.clock())
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_size:
                self._entries.popitem(last=False)   # evict the least recent

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class CachedClient:
    """Wraps a client, serving repeated deterministic requests from memory."""

    def __init__(self, inner: Any, cache: ResponseCache | None = None) -> None:
        self.inner = inner
        # `cache or ResponseCache()` would DISCARD a passed-in empty cache:
        # ResponseCache defines __len__, so an empty one is falsy.
        self.cache = cache if cache is not None else ResponseCache()

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        # temperature > 0 means the caller wants variation; do not take it away
        if kwargs.get("temperature", 0.0):
            return self.inner.chat(messages, **kwargs)

        key = cache_key(messages, **kwargs)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        response = self.inner.chat(messages, **kwargs)
        self.cache.put(key, response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


# ----------------------------------------------------------- circuit breaker


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


# --------------------------------------------------------------- rate limits


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


# ------------------------------------------------------------- budget guard


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
