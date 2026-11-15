"""Tests for Chapter 13, Exercise 1 — caching."""

import pytest

from agentlib.testing import FakeLLMClient
from chapters.ch13_hardening.exercises.exercise_1_cache import (
    CachedClient,
    ResponseCache,
    cache_key,
)

MSGS = [{"role": "user", "content": "hello"}]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestCacheKey:
    def test_deterministic(self):
        assert cache_key(MSGS) == cache_key(MSGS)

    def test_different_messages_differ(self):
        assert cache_key(MSGS) != cache_key([{"role": "user", "content": "other"}])

    def test_temperature_is_part_of_the_key(self):
        # a key on messages alone serves the wrong answer, intermittently
        assert cache_key(MSGS, temperature=0.0) != cache_key(MSGS, temperature=0.7)

    def test_tools_are_part_of_the_key(self):
        tools = [{"type": "function", "function": {"name": "search"}}]
        assert cache_key(MSGS) != cache_key(MSGS, tools=tools)

    def test_model_is_part_of_the_key(self):
        assert cache_key(MSGS, model="a") != cache_key(MSGS, model="b")

    def test_param_order_does_not_matter(self):
        assert cache_key(MSGS, a=1, b=2) == cache_key(MSGS, b=2, a=1)

    def test_none_params_are_ignored(self):
        assert cache_key(MSGS) == cache_key(MSGS, temperature=None)

    def test_survives_unserialisable_params(self):
        cache_key(MSGS, weird=object())   # must not raise

    def test_is_a_short_hex_string(self):
        key = cache_key(MSGS)
        assert len(key) == 32
        int(key, 16)


class TestResponseCache:
    def test_miss_then_hit(self):
        c = ResponseCache()
        assert c.get("k") is None
        c.put("k", "value")
        assert c.get("k") == "value"

    def test_counts(self):
        c = ResponseCache()
        c.get("k")
        c.put("k", "v")
        c.get("k")
        assert c.misses == 1 and c.hits == 1
        assert c.hit_rate == pytest.approx(0.5)

    def test_hit_rate_with_no_traffic(self):
        assert ResponseCache().hit_rate == 0.0

    def test_len(self):
        c = ResponseCache()
        c.put("a", 1)
        c.put("b", 2)
        assert len(c) == 2

    def test_clear(self):
        c = ResponseCache()
        c.put("a", 1)
        c.clear()
        assert len(c) == 0


class TestTTL:
    def test_expires(self):
        clock = Clock()
        c = ResponseCache(ttl_s=10, clock=clock)
        c.put("k", "v")
        clock.now = 5
        assert c.get("k") == "v"
        clock.now = 11
        assert c.get("k") is None

    def test_expired_entry_is_removed(self):
        clock = Clock()
        c = ResponseCache(ttl_s=10, clock=clock)
        c.put("k", "v")
        clock.now = 11
        c.get("k")
        assert len(c) == 0

    def test_no_ttl_never_expires(self):
        clock = Clock()
        c = ResponseCache(ttl_s=None, clock=clock)
        c.put("k", "v")
        clock.now = 10_000_000
        assert c.get("k") == "v"


class TestLRU:
    def test_evicts_when_full(self):
        c = ResponseCache(max_size=2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        assert len(c) == 2
        assert c.get("a") is None

    def test_reading_makes_an_entry_recent(self):
        c = ResponseCache(max_size=2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")          # touch 'a'
        c.put("c", 3)       # should evict 'b', not 'a'
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_rewriting_makes_an_entry_recent(self):
        c = ResponseCache(max_size=2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 10)
        c.put("c", 3)
        assert c.get("a") == 10
        assert c.get("b") is None


class TestCachedClient:
    def test_second_identical_call_is_served_from_cache(self):
        inner = FakeLLMClient(["first", "second"])
        client = CachedClient(inner)
        assert client.chat(MSGS).text == "first"
        assert client.chat(MSGS).text == "first"
        assert inner.call_count == 1

    def test_different_messages_call_through(self):
        inner = FakeLLMClient(["one", "two"])
        client = CachedClient(inner)
        client.chat(MSGS)
        client.chat([{"role": "user", "content": "different"}])
        assert inner.call_count == 2

    def test_temperature_above_zero_bypasses_the_cache(self):
        # the caller asked for variation; serving a cached answer removes it
        inner = FakeLLMClient(["one", "two", "three"])
        client = CachedClient(inner)
        client.chat(MSGS, temperature=0.8)
        client.chat(MSGS, temperature=0.8)
        assert inner.call_count == 2

    def test_temperature_zero_is_cached(self):
        inner = FakeLLMClient(["one", "two"])
        client = CachedClient(inner)
        client.chat(MSGS, temperature=0.0)
        client.chat(MSGS, temperature=0.0)
        assert inner.call_count == 1

    def test_shared_cache_between_clients(self):
        cache = ResponseCache()
        a = CachedClient(FakeLLMClient(["from a"]), cache)
        b = CachedClient(FakeLLMClient(["from b"]), cache)
        assert a.chat(MSGS).text == "from a"
        assert b.chat(MSGS).text == "from a"

    def test_delegates_other_attributes(self):
        inner = FakeLLMClient(["x"])
        assert CachedClient(inner).model == inner.model

    def test_exceptions_are_not_cached(self):
        inner = FakeLLMClient([RuntimeError("boom"), "recovered"])
        client = CachedClient(inner)
        with pytest.raises(RuntimeError):
            client.chat(MSGS)
        assert client.chat(MSGS).text == "recovered"
