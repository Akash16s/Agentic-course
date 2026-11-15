"""SOLUTION — Chapter 15, Exercise 4."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def gather_bounded(coros: list[Any], *, limit: int = 8) -> list[Any]:
    """`asyncio.gather` with a concurrency cap.

    Plain `gather` on 500 coroutines opens 500 connections at once, which is how
    you rate-limit yourself into a wall. A semaphore is four lines and turns that
    into a queue.
    """
    semaphore = asyncio.Semaphore(limit)

    async def run(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(run(c) for c in coros))


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    # everything blocking goes through a thread, or it freezes every other user
    return await asyncio.to_thread(fn, *args, **kwargs)


class ConcurrencyTracker:
    def __init__(self) -> None:
        self.live = 0
        self.peak = 0

    async def __aenter__(self) -> "ConcurrencyTracker":
        # no lock: asyncio is single-threaded and there is no await between the
        # read and the write. The danger is never the increment, it is an await
        # in the middle of one.
        self.live += 1
        self.peak = max(self.peak, self.live)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.live -= 1
