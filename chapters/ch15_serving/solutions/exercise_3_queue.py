"""SOLUTION — Chapter 15, Exercise 3."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from .exercise_2_runstore import Run, RunStatus, RunStore


class JobQueue:
    """An in-process work queue with a bounded buffer and N worker threads.

    BOUNDED on purpose. An unbounded queue turns a traffic spike into unbounded
    memory growth and a latency curve that goes vertical — users wait ten minutes
    for a request that should have been refused in ten milliseconds. Back-pressure
    (rejecting when full) is kinder than accepting work you cannot do.

    In production this is Redis, SQS or a database table. The semantics you need
    are the same, which is why building the small one is worth an hour.
    """

    def __init__(
        self,
        handler: Callable[[Run], None],
        store: RunStore,
        *,
        workers: int = 2,
        max_queued: int = 100,
    ) -> None:
        self.handler = handler
        self.store = store
        self.max_queued = max_queued
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=max_queued)
        self._threads: list[threading.Thread] = []
        self._running = False
        self.workers = workers

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for index in range(self.workers):
            thread = threading.Thread(target=self._work, name=f"worker-{index}",
                                      daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Ask every worker to finish and wait briefly.

        A `None` sentinel per worker, rather than a flag, so a worker blocked on
        `get()` wakes up immediately instead of after its poll interval.
        """
        self._running = False
        for _ in self._threads:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    def submit(self, task: str, *, session_id: str = "default") -> Run:
        """Enqueue work. Raises `queue.Full` rather than blocking when saturated."""
        run = self.store.create(task, session_id=session_id)
        try:
            self._queue.put_nowait(run.id)
        except queue.Full:
            run.status = RunStatus.FAILED
            run.error = "queue is full; try again shortly"
            self.store.save(run)
            raise
        return run

    def _work(self) -> None:
        while self._running:
            try:
                run_id = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if run_id is None:
                self._queue.task_done()
                return
            try:
                self._process(run_id)
            finally:
                self._queue.task_done()

    def _process(self, run_id: str) -> None:
        run = self.store.get(run_id)
        if run is None or run.status is RunStatus.CANCELLED:
            return
        run.status = RunStatus.RUNNING
        run.attempts += 1
        self.store.save(run)
        try:
            self.handler(run)
        except Exception as exc:  # noqa: BLE001 - one bad job must not kill a worker
            run.status = RunStatus.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
        else:
            if not run.terminal:
                run.status = RunStatus.SUCCEEDED
        self.store.save(run)
