"""EXERCISE 4 — Async concurrency.

    pytest chapters/ch15_serving/tests -q -k async
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def gather_bounded(coros: list[Awaitable[Any]], *, limit: int = 8) -> list[Any]:
    """`asyncio.gather` with a concurrency cap. Results in INPUT ORDER.

    Spec:
        semaphore = asyncio.Semaphore(limit)
        async def run(coro):
            async with semaphore:
                return await coro
        return await asyncio.gather(*(run(c) for c in coros))

    Plain `gather` over 500 coroutines opens 500 connections at once, which
    rate-limits you into a wall and is usually SLOWER end to end than a bounded
    version. Four lines to fix.

    `asyncio.gather` preserves input order regardless of completion order, which
    is what callers expect.
    """
    # TODO: implement
    raise NotImplementedError


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a blocking function without freezing the event loop.

    `await asyncio.to_thread(fn, *args, **kwargs)`

    THE ONE RULE OF ASYNC SERVING: never call a blocking function inside a
    coroutine. One `requests.get()`, one `time.sleep()`, one heavy parse in one
    tool freezes the ENTIRE loop — every other user's request stops until it
    returns.

    It is invisible in development, because with one user there is nothing else to
    freeze. Under load it presents as "the service is slow" with no slow span
    anywhere in your traces, because the time is spent waiting to be scheduled.
    """
    # TODO: implement
    raise NotImplementedError


class ConcurrencyTracker:
    """Records peak concurrency, so the tests can PROVE the cap works.

    `async with tracker:` increments on entry, decrements on exit, and remembers
    the high-water mark in `self.peak`.

    No lock needed: asyncio is single-threaded and there is no await between the
    read and the write. Getting that reasoning right is half of understanding
    async — the danger is never the increment, it is what happens across an
    `await`.
    """

    def __init__(self) -> None:
        # TODO: implement (self.live = 0, self.peak = 0)
        raise NotImplementedError

    async def __aenter__(self) -> "ConcurrencyTracker":
        # TODO: implement
        raise NotImplementedError

    async def __aexit__(self, *exc: Any) -> None:
        # TODO: implement
        raise NotImplementedError
