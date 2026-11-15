"""SOLUTION — Chapter 10, Exercise 4."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .exercise_1_dataset import Dataset, EvalCase
from .exercise_2_checks import Check, CheckResult
from .exercise_3_results import CaseResult, EvalReport


class EvalRunner:
    """Run an agent over a dataset and score it.

    `run_case(input) -> Any` is injected. It can return a string or an AgentResult;
    the checks handle both.
    """

    def __init__(
        self,
        run_case: Callable[[str], Any],
        checks: list[Check],
        *,
        max_parallel: int = 4,
        on_result: Callable[[CaseResult], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.run_case = run_case
        self.checks = checks
        self.max_parallel = max_parallel
        self.on_result = on_result
        self.clock = clock

    def run_one(self, case: EvalCase) -> CaseResult:
        """Run and score one case. NEVER raises — an exception is a failed case,
        not a failed suite. One crashing case must not cost you the other 199."""
        started = self.clock()
        try:
            output = self.run_case(case.input)
        except Exception as exc:  # noqa: BLE001
            return CaseResult(case=case, error=f"{type(exc).__name__}: {exc}",
                              duration_s=self.clock() - started)

        checks = []
        for check in self.checks:
            try:
                checks.append(check(output, case))
            except Exception as exc:  # noqa: BLE001
                checks.append(CheckResult("check_error", False, str(exc)))

        return CaseResult(
            case=case,
            checks=checks,
            output=output,
            duration_s=self.clock() - started,
            cost=float(getattr(output, "cost", 0.0) or 0.0),
        )

    def run(self, dataset: Dataset) -> EvalReport:
        started = self.clock()
        if self.max_parallel <= 1 or len(dataset) <= 1:
            results = [self.run_one(c) for c in dataset]
        else:
            with ThreadPoolExecutor(
                max_workers=min(self.max_parallel, len(dataset))
            ) as pool:
                results = list(pool.map(self.run_one, dataset.cases))

        if self.on_result is not None:
            for result in results:
                self.on_result(result)

        return EvalReport(name=dataset.name, results=results,
                          duration_s=self.clock() - started)
