"""SOLUTION — Chapter 13, Exercise 1."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from agentlib.llm import LLMResponse, Message


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
