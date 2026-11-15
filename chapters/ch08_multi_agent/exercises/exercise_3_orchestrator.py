"""EXERCISE 3 — Orchestrator / worker fan-out.

    pytest chapters/ch08_multi_agent/tests -q -k orchestrator
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable


@dataclass
class WorkerResult:
    """Fields: name: str, task: str, output: str = "", error: str|None = None,
               duration_s: float = 0.0"""

    name: str
    task: str

    @property
    def ok(self) -> bool:
        """True when `error` is None."""
        # TODO: implement
        raise NotImplementedError


class Orchestrator:
    """Run independent subtasks concurrently and collect the results.

    __init__(self, workers: dict[str, Callable[[str], str]], *, max_parallel=4,
             on_result=None, clock=time.monotonic)

    Workers are plain callables. The orchestrator does not know or care whether a
    worker is an agent, a chain or a function — which is exactly why this class can
    be tested in milliseconds.
    """

    def __init__(
        self,
        workers: dict[str, Callable[[str], str]],
        *,
        max_parallel: int = 4,
        on_result: Callable[[WorkerResult], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def run_one(self, name: str, task: str) -> WorkerResult:
        """Run one worker. NEVER RAISES.

        Spec:
          * unknown name -> WorkerResult(error=f"no worker named {name!r}")
          * worker raises -> WorkerResult(error=f"{type(exc).__name__}: {exc}")
          * success -> WorkerResult(output=str(result))
          * record duration_s in every case that actually ran

        Partial results are worth far more than none. Three of four research
        subtasks succeeding is a usable answer with a caveat; an exception is
        nothing at all.
        """
        # TODO: implement
        raise NotImplementedError

    def fan_out(self, assignments: list[tuple[str, str]]) -> list[WorkerResult]:
        """Run (worker_name, task) pairs concurrently. Results in INPUT ORDER.

        Spec:
          * [] -> []
          * one assignment, or max_parallel <= 1 -> run serially
          * otherwise ThreadPoolExecutor with min(max_parallel, len(assignments))
            workers and `pool.map` (which preserves order)
          * call `on_result` for each result, after they are all collected

        CAP THE CONCURRENCY. Twenty parallel workers against one provider is twenty
        rate-limit errors and a slower run than four at a time.
        """
        # TODO: implement
        raise NotImplementedError
