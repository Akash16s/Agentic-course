"""EXERCISE 3 — The job queue.

    pytest chapters/ch15_serving/tests -q -k queue
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

from .exercise_2_runstore import Run, RunStatus, RunStore


class JobQueue:
    """A bounded in-process work queue with N worker threads.

    __init__(self, handler: Callable[[Run], None], store: RunStore, *,
             workers: int = 2, max_queued: int = 100)

    Use `queue.Queue(maxsize=max_queued)` holding run IDs (strings), plus a `None`
    sentinel for shutdown.

    BOUNDED ON PURPOSE. An unbounded queue turns a traffic spike into unbounded
    memory and a latency curve that goes vertical: users wait ten minutes for
    something that should have been refused in ten milliseconds. Back-pressure is
    kinder than false hope.
    """

    def __init__(
        self,
        handler: Callable[[Run], None],
        store: RunStore,
        *,
        workers: int = 2,
        max_queued: int = 100,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def start(self) -> None:
        """Spawn `workers` daemon threads running `self._work`. Idempotent."""
        # TODO: implement
        raise NotImplementedError

    def stop(self, *, timeout: float = 5.0) -> None:
        """Signal shutdown and join.

        Put ONE `None` PER WORKER, rather than only flipping a flag. A worker
        blocked in `get()` wakes on the sentinel immediately; with a flag alone it
        sleeps out its poll timeout first, and shutdown takes `workers * timeout`
        seconds — which is how a rolling deploy starts taking minutes.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def depth(self) -> int:
        """Queued items. This is the number you autoscale on — an agent worker is
        ~0% CPU and 100% waiting, so CPU-based autoscaling never fires."""
        # TODO: implement
        raise NotImplementedError

    def submit(self, task: str, *, session_id: str = "default") -> Run:
        """Create a run and enqueue it.

        Spec:
          * store.create(...)
          * `put_nowait` the run id
          * on queue.Full: mark the run FAILED with a "queue is full" error, save
            it, and RE-RAISE so the caller can return a 503

        Rejecting fast is the whole point of a bounded queue. Blocking here would
        hold an HTTP worker hostage and just move the queue somewhere less visible.
        """
        # TODO: implement
        raise NotImplementedError

    def _work(self) -> None:
        """Worker loop: `get(timeout=0.1)`, skip on Empty, return on the `None`
        sentinel, otherwise `self._process(run_id)`. Always `task_done()`."""
        # TODO: implement
        raise NotImplementedError

    def _process(self, run_id: str) -> None:
        """Run one job.

        Spec:
          * load it; missing or CANCELLED -> return without running
          * status = RUNNING, attempts += 1, SAVE (this is the heartbeat
            reclaim_stale depends on)
          * call self.handler(run) inside try/except
          * exception -> status = FAILED, error = f"{type}: {exc}"
          * no exception and the handler did not already set a terminal status ->
            SUCCEEDED
          * save

        CATCH Exception. One bad job must fail the RUN, never the WORKER. A worker
        that dies on a malformed task takes all its future work with it, and the
        symptom is "throughput slowly drops to zero" hours later.
        """
        # TODO: implement
        raise NotImplementedError
