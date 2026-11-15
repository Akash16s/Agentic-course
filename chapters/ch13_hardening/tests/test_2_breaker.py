"""Tests for Chapter 13, Exercise 2 — the circuit breaker."""

import pytest

from chapters.ch13_hardening.exercises.exercise_2_breaker import (
    BreakerState,
    CircuitBreaker,
    CircuitOpen,
)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def fail():
    raise RuntimeError("service down")


def succeed():
    return "ok"


class TestStates:
    def test_three_states(self):
        assert {s.value for s in BreakerState} == {"closed", "open", "half_open"}

    def test_starts_closed(self):
        assert CircuitBreaker().state is BreakerState.CLOSED

    def test_opens_after_the_threshold(self):
        b = CircuitBreaker(failure_threshold=3)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                b.call(fail)
        assert b.state is BreakerState.CLOSED
        with pytest.raises(RuntimeError):
            b.call(fail)
        assert b.state is BreakerState.OPEN

    def test_open_rejects_without_calling(self):
        b = CircuitBreaker(failure_threshold=1)
        with pytest.raises(RuntimeError):
            b.call(fail)
        called = []
        with pytest.raises(CircuitOpen):
            b.call(lambda: called.append(1))
        assert called == [], "an open breaker must not invoke the function"

    def test_circuit_open_is_not_retryable(self):
        assert CircuitOpen("x").retryable is False

    def test_half_open_after_the_timeout(self):
        clock = Clock()
        b = CircuitBreaker(failure_threshold=1, reset_timeout_s=10, clock=clock)
        with pytest.raises(RuntimeError):
            b.call(fail)
        assert b.state is BreakerState.OPEN
        clock.now = 9
        assert b.state is BreakerState.OPEN
        clock.now = 10
        assert b.state is BreakerState.HALF_OPEN

    def test_closes_after_enough_probes(self):
        clock = Clock()
        b = CircuitBreaker(failure_threshold=1, reset_timeout_s=10,
                           success_threshold=2, clock=clock)
        with pytest.raises(RuntimeError):
            b.call(fail)
        clock.now = 11
        b.call(succeed)
        assert b.state is BreakerState.HALF_OPEN
        b.call(succeed)
        assert b.state is BreakerState.CLOSED

    def test_a_failed_probe_reopens_for_the_full_timeout(self):
        # half a recovery is not a recovery
        clock = Clock()
        b = CircuitBreaker(failure_threshold=3, reset_timeout_s=10, clock=clock)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                b.call(fail)
        clock.now = 11
        assert b.state is BreakerState.HALF_OPEN
        with pytest.raises(RuntimeError):
            b.call(fail)
        assert b.state is BreakerState.OPEN
        clock.now = 20
        assert b.state is BreakerState.OPEN, "the timeout should have restarted"
        clock.now = 22
        assert b.state is BreakerState.HALF_OPEN


class TestConsecutive:
    def test_success_resets_the_failure_count(self):
        # a lifetime tally trips a healthy service eventually, for no findable reason
        b = CircuitBreaker(failure_threshold=3)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                b.call(fail)
        b.call(succeed)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                b.call(fail)
        assert b.state is BreakerState.CLOSED

    def test_intermittent_failures_do_not_open_it(self):
        b = CircuitBreaker(failure_threshold=3)
        for _ in range(20):
            with pytest.raises(RuntimeError):
                b.call(fail)
            b.call(succeed)
        assert b.state is BreakerState.CLOSED


class TestCall:
    def test_returns_the_result(self):
        assert CircuitBreaker().call(lambda: 42) == 42

    def test_re_raises_the_original_exception(self):
        with pytest.raises(RuntimeError, match="service down"):
            CircuitBreaker().call(fail)

    def test_allow(self):
        b = CircuitBreaker(failure_threshold=1)
        assert b.allow()
        with pytest.raises(RuntimeError):
            b.call(fail)
        assert not b.allow()

    def test_error_message_mentions_the_wait(self):
        b = CircuitBreaker(failure_threshold=1, reset_timeout_s=30)
        with pytest.raises(RuntimeError):
            b.call(fail)
        with pytest.raises(CircuitOpen) as exc:
            b.call(succeed)
        assert "30" in str(exc.value) or "29" in str(exc.value)

    def test_the_fast_failure_is_the_point(self):
        # without a breaker every one of these would wait for a timeout
        b = CircuitBreaker(failure_threshold=1)
        with pytest.raises(RuntimeError):
            b.call(fail)
        for _ in range(100):
            with pytest.raises(CircuitOpen):
                b.call(fail)
