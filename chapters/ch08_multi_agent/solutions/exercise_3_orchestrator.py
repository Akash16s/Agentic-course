"""SOLUTION — Chapter 8, Exercise 3."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable


@dataclass
class WorkerResult:
    name: str
    task: str
    output: str = ""
    error: str | None = None
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


class Orchestrator:
    """Fan out independent subtasks to workers, gather the results, synthesise.

    Workers are `Callable[[str], str]`. They can be agents, chains, or plain
    functions — the orchestrator does not care, which is what makes it testable.
    """

    def __init__(
        self,
        workers: dict[str, Callable[[str], str]],
        *,
        max_parallel: int = 4,
        on_result: Callable[[WorkerResult], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.workers = workers
        self.max_parallel = max_parallel
        self.on_result = on_result
        self.clock = clock

    def run_one(self, name: str, task: str) -> WorkerResult:
        worker = self.workers.get(name)
        if worker is None:
            return WorkerResult(name=name, task=task,
                                error=f"no worker named {name!r}")
        started = self.clock()
        try:
            output = worker(task)
        except Exception as exc:  # noqa: BLE001 - one worker must not kill the run
            return WorkerResult(name=name, task=task, error=f"{type(exc).__name__}: {exc}",
                                duration_s=self.clock() - started)
        return WorkerResult(name=name, task=task, output=str(output),
                            duration_s=self.clock() - started)

    def fan_out(self, assignments: list[tuple[str, str]]) -> list[WorkerResult]:
        """Run (worker_name, task) pairs concurrently. Results keep input order.

        A failing worker produces a WorkerResult with `error` set, never an
        exception. Partial results are worth far more than none: three of four
        research subtasks succeeding is a usable answer with a caveat.
        """
        if not assignments:
            return []
        if len(assignments) == 1 or self.max_parallel <= 1:
            results = [self.run_one(name, task) for name, task in assignments]
        else:
            with ThreadPoolExecutor(
                max_workers=min(self.max_parallel, len(assignments))
            ) as pool:
                results = list(pool.map(lambda a: self.run_one(*a), assignments))
        if self.on_result is not None:
            for result in results:
                self.on_result(result)
        return results
