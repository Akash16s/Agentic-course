"""Tests for Chapter 15, Exercise 4 — async concurrency."""

import asyncio
import time

import pytest

from chapters.ch15_serving.exercises.exercise_4_async import (
    ConcurrencyTracker,
    gather_bounded,
    run_blocking,
)


class TestGatherBounded:
    def test_returns_all_results(self):
        async def main():
            async def job(i):
                await asyncio.sleep(0.001)
                return i

            return await gather_bounded([job(i) for i in range(10)], limit=3)

        assert asyncio.run(main()) == list(range(10))

    def test_preserves_input_order(self):
        async def main():
            async def job(i):
                await asyncio.sleep((10 - i) * 0.005)   # later items finish first
                return i

            return await gather_bounded([job(i) for i in range(6)], limit=6)

        assert asyncio.run(main()) == list(range(6))

    def test_respects_the_limit(self):
        async def main():
            tracker = ConcurrencyTracker()

            async def job(i):
                async with tracker:
                    await asyncio.sleep(0.02)
                return i

            await gather_bounded([job(i) for i in range(20)], limit=4)
            return tracker.peak

        assert asyncio.run(main()) <= 4

    def test_unbounded_would_open_everything_at_once(self):
        # what gather() alone does, and why the semaphore is worth four lines
        async def main():
            tracker = ConcurrencyTracker()

            async def job(i):
                async with tracker:
                    await asyncio.sleep(0.02)

            await asyncio.gather(*(job(i) for i in range(20)))
            return tracker.peak

        assert asyncio.run(main()) == 20

    def test_empty(self):
        assert asyncio.run(gather_bounded([])) == []

    def test_a_limit_above_the_count(self):
        async def main():
            async def job(i):
                return i

            return await gather_bounded([job(i) for i in range(3)], limit=100)

        assert asyncio.run(main()) == [0, 1, 2]

    def test_is_actually_concurrent(self):
        async def main():
            async def job(i):
                await asyncio.sleep(0.05)
                return i

            started = time.monotonic()
            await gather_bounded([job(i) for i in range(8)], limit=8)
            return time.monotonic() - started

        assert asyncio.run(main()) < 0.2


class TestRunBlocking:
    def test_returns_the_value(self):
        assert asyncio.run(run_blocking(sum, [1, 2, 3])) == 6

    def test_passes_kwargs(self):
        assert asyncio.run(run_blocking(sorted, [3, 1, 2], reverse=True)) == [3, 2, 1]

    def test_does_not_block_the_loop(self):
        # the whole point: a blocking call must not stop everything else
        async def main():
            ticks = []

            async def ticker():
                for _ in range(8):
                    await asyncio.sleep(0.01)
                    ticks.append(1)

            await asyncio.gather(run_blocking(time.sleep, 0.06), ticker())
            return len(ticks)

        assert asyncio.run(main()) == 8, "the event loop stalled"

    def test_propagates_exceptions(self):
        def boom():
            raise ValueError("x")

        with pytest.raises(ValueError):
            asyncio.run(run_blocking(boom))


class TestConcurrencyTracker:
    def test_tracks_the_peak(self):
        async def main():
            tracker = ConcurrencyTracker()

            async def job():
                async with tracker:
                    await asyncio.sleep(0.02)

            await asyncio.gather(*(job() for _ in range(5)))
            return tracker.peak, tracker.live

        peak, live = asyncio.run(main())
        assert peak == 5
        assert live == 0, "the counter leaked"

    def test_decrements_on_an_exception(self):
        async def main():
            tracker = ConcurrencyTracker()
            try:
                async with tracker:
                    raise ValueError("x")
            except ValueError:
                pass
            return tracker.live

        assert asyncio.run(main()) == 0
