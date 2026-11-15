"""Tests for Chapter 13, Exercise 4 — budget guards and idempotency."""

import pytest

from agentlib import errors
from chapters.ch13_hardening.exercises.exercise_4_guards import (
    BudgetGuard,
    IdempotencyStore,
    mark_cacheable_prefix,
)

MSGS = [{"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "hello"}]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestBudgetGuard:
    def test_allows_within_budget(self):
        BudgetGuard(1.0).check()

    def test_remaining(self):
        guard = BudgetGuard(1.0)
        guard.record(0.25)
        assert guard.remaining == pytest.approx(0.75)

    def test_raises_once_over(self):
        guard = BudgetGuard(1.0)
        guard.record(1.5)
        with pytest.raises(errors.BudgetExceeded):
            guard.check()

    def test_preflight_refuses_before_spending(self):
        # the difference from Chapter 1: this stops the call HAPPENING
        guard = BudgetGuard(1.0, estimate=lambda m: 2.0)
        with pytest.raises(errors.BudgetExceeded):
            guard.check(MSGS)
        assert guard.spent == 0.0, "nothing was spent; that is the point"

    def test_preflight_allows_an_affordable_call(self):
        guard = BudgetGuard(1.0, estimate=lambda m: 0.1)
        guard.check(MSGS)

    def test_estimate_accumulates_with_spend(self):
        guard = BudgetGuard(1.0, estimate=lambda m: 0.3)
        guard.record(0.8)
        with pytest.raises(errors.BudgetExceeded):
            guard.check(MSGS)

    def test_no_estimator_still_guards(self):
        guard = BudgetGuard(1.0)
        guard.record(1.1)
        with pytest.raises(errors.BudgetExceeded):
            guard.check(MSGS)

    def test_exception_carries_the_numbers(self):
        guard = BudgetGuard(1.0, estimate=lambda m: 5.0)
        with pytest.raises(errors.BudgetExceeded) as exc:
            guard.check(MSGS)
        assert exc.value.budget == 1.0
        assert exc.value.spent == pytest.approx(5.0)


class TestIdempotencyStore:
    def test_runs_once(self):
        runs = []
        store = IdempotencyStore()
        for _ in range(5):
            store.run("refund-42", lambda: runs.append(1) or "refunded")
        assert len(runs) == 1

    def test_returns_the_stored_result(self):
        store = IdempotencyStore()
        first = store.run("k", lambda: "the answer")
        second = store.run("k", lambda: "a different answer")
        assert first == second == "the answer"

    def test_different_keys_run_separately(self):
        runs = []
        store = IdempotencyStore()
        store.run("a", lambda: runs.append(1))
        store.run("b", lambda: runs.append(1))
        assert len(runs) == 2

    def test_seen(self):
        store = IdempotencyStore()
        assert not store.seen("k")
        store.run("k", lambda: "x")
        assert store.seen("k")

    def test_expires(self):
        clock = Clock()
        store = IdempotencyStore(ttl_s=10, clock=clock)
        runs = []
        store.run("k", lambda: runs.append(1))
        clock.now = 11
        assert not store.seen("k")
        store.run("k", lambda: runs.append(1))
        assert len(runs) == 2

    def test_a_failure_is_not_stored(self):
        # an operation that raised did not happen; the retry may try again
        store = IdempotencyStore()
        with pytest.raises(RuntimeError):
            store.run("k", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert not store.seen("k")
        assert store.run("k", lambda: "worked") == "worked"

    def test_in_flight_key_is_rejected(self):
        # two concurrent retries must not BOTH start the work
        store = IdempotencyStore()

        def reentrant():
            with pytest.raises(errors.LLMError):
                store.run("k", lambda: "should not run")
            return "outer"

        assert store.run("k", reentrant) == "outer"

    def test_in_flight_is_cleared_after_a_failure(self):
        store = IdempotencyStore()
        with pytest.raises(RuntimeError):
            store.run("k", lambda: (_ for _ in ()).throw(RuntimeError("x")))
        store.run("k", lambda: "now fine")


class TestCacheablePrefix:
    def test_marks_the_first_message(self):
        out = mark_cacheable_prefix(MSGS)
        assert out[0]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in out[1]

    def test_marks_several(self):
        out = mark_cacheable_prefix(MSGS, upto=2)
        assert all("cache_control" in m for m in out)

    def test_does_not_mutate_the_input(self):
        original = [dict(m) for m in MSGS]
        mark_cacheable_prefix(MSGS)
        assert MSGS == original

    def test_returns_new_dicts(self):
        out = mark_cacheable_prefix(MSGS)
        assert out[0] is not MSGS[0]

    def test_preserves_content(self):
        out = mark_cacheable_prefix(MSGS)
        assert out[0]["content"] == "you are helpful"
        assert out[0]["role"] == "system"

    def test_empty(self):
        assert mark_cacheable_prefix([]) == []

    def test_upto_larger_than_the_list(self):
        out = mark_cacheable_prefix(MSGS, upto=99)
        assert len(out) == 2
