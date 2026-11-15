"""Tests for Chapter 13, Exercise 3 — the token bucket."""

import pytest

from chapters.ch13_hardening.exercises.exercise_3_ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestConstruction:
    def test_rejects_a_non_positive_rate(self):
        with pytest.raises(ValueError):
            RateLimiter(0)
        with pytest.raises(ValueError):
            RateLimiter(-1)

    def test_capacity_defaults_to_rate(self):
        assert RateLimiter(5).capacity == 5

    def test_starts_full(self):
        assert RateLimiter(5, capacity=10).tokens == 10


class TestAcquire:
    def test_take_one(self):
        limiter = RateLimiter(5, clock=Clock())
        assert limiter.try_acquire()
        assert limiter.tokens == pytest.approx(4)

    def test_exhausts(self):
        limiter = RateLimiter(3, clock=Clock())
        assert [limiter.try_acquire() for _ in range(5)] == [True, True, True, False, False]

    def test_burst_up_to_capacity(self):
        # the reason for a bucket rather than a fixed window
        limiter = RateLimiter(2, capacity=10, clock=Clock())
        assert all(limiter.try_acquire() for _ in range(10))
        assert not limiter.try_acquire()

    def test_multiple_permits(self):
        limiter = RateLimiter(10, clock=Clock())
        assert limiter.try_acquire(5)
        assert limiter.tokens == pytest.approx(5)
        assert not limiter.try_acquire(6)

    def test_never_blocks(self):
        limiter = RateLimiter(1, clock=Clock())
        limiter.try_acquire()
        assert limiter.try_acquire() is False


class TestRefill:
    def test_refills_over_time(self):
        clock = Clock()
        limiter = RateLimiter(2, capacity=2, clock=clock)
        limiter.try_acquire(2)
        assert limiter.tokens == pytest.approx(0)
        clock.now = 0.5
        assert limiter.tokens == pytest.approx(1)
        clock.now = 1.0
        assert limiter.tokens == pytest.approx(2)

    def test_never_exceeds_capacity(self):
        clock = Clock()
        limiter = RateLimiter(5, capacity=5, clock=clock)
        clock.now = 1_000
        assert limiter.tokens == 5

    def test_sustained_rate(self):
        clock = Clock()
        limiter = RateLimiter(10, capacity=10, clock=clock)
        taken = 0
        for step in range(100):
            clock.now = step * 0.1        # 10 seconds total
            if limiter.try_acquire():
                taken += 1
        assert 90 <= taken <= 110, f"expected ~100 permits in 10s, got {taken}"


class TestTimeUntil:
    def test_zero_when_available(self):
        assert RateLimiter(5, clock=Clock()).time_until() == 0.0

    def test_computes_the_wait(self):
        clock = Clock()
        limiter = RateLimiter(2, capacity=2, clock=clock)
        limiter.try_acquire(2)
        assert limiter.time_until(1) == pytest.approx(0.5)
        assert limiter.time_until(2) == pytest.approx(1.0)

    def test_accounts_for_partial_refill(self):
        clock = Clock()
        limiter = RateLimiter(2, capacity=4, clock=clock)
        limiter.try_acquire(4)
        clock.now = 0.5             # one token back
        assert limiter.time_until(3) == pytest.approx(1.0)


class TestBlockingAcquire:
    def test_returns_immediately_when_available(self):
        slept = []
        RateLimiter(5, clock=Clock()).acquire(sleep=slept.append)
        assert slept == []

    def test_sleeps_then_succeeds(self):
        clock = Clock()
        limiter = RateLimiter(1, capacity=1, clock=clock)
        limiter.try_acquire()

        slept = []

        def sleep(seconds):
            slept.append(seconds)
            clock.now += seconds

        limiter.acquire(sleep=sleep)
        assert slept
        assert sum(slept) == pytest.approx(1.0, abs=0.05)

    def test_does_not_spin(self):
        # a zero sleep on a contended bucket burns a core
        clock = Clock()
        limiter = RateLimiter(1, capacity=1, clock=clock)
        limiter.try_acquire()
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            clock.now += max(seconds, 0.001)

        limiter.acquire(sleep=sleep)
        assert all(s > 0 for s in slept)
        assert len(slept) < 100
