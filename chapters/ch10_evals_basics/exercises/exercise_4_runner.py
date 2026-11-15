"""EXERCISE 4 — The runner.

    pytest chapters/ch10_evals_basics/tests -q -k runner
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .exercise_1_dataset import Dataset, EvalCase
from .exercise_2_checks import Check, CheckResult
from .exercise_3_results import CaseResult, EvalReport


class EvalRunner:
    """Run an agent over a dataset and score it.

    __init__(self, run_case: Callable[[str], Any], checks: list[Check], *,
             max_parallel: int = 4, on_result=None, clock=time.monotonic)

    `run_case` is injected and may return a plain string or an AgentResult — the
    checks handle both. That is what lets the entire test suite for this chapter
    run offline in milliseconds.
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
        # TODO: implement
        raise NotImplementedError

    def run_one(self, case: EvalCase) -> CaseResult:
        """Run and score one case. NEVER RAISES.

        Spec:
          started = clock()
          try: output = self.run_case(case.input)
          except Exception as exc:
              return CaseResult(case=case, error=f"{type(exc).__name__}: {exc}",
                                duration_s=clock()-started)

          for each check:
              try: append check(output, case)
              except Exception as exc:
                  append CheckResult("check_error", False, str(exc))

          return CaseResult(case, checks, output,
                            duration_s=clock()-started,
                            cost=float(getattr(output, "cost", 0.0) or 0.0))

        TWO SEPARATE try/excepts, deliberately. A crashing AGENT is a failed case.
        A crashing CHECK is a failed check. Neither is allowed to cost you the
        other 199 results — an eval suite that dies on case 3 of 200 is useless
        exactly when you need it most.
        """
        # TODO: implement
        raise NotImplementedError

    def run(self, dataset: Dataset) -> EvalReport:
        """Run every case and build the report.

        Spec:
          * max_parallel <= 1, or a single case -> serial
          * otherwise ThreadPoolExecutor, min(max_parallel, len(dataset)) workers,
            `pool.map` (order preserved — a report whose rows move between runs is
            miserable to diff)
          * call on_result for each result after collection
          * return EvalReport(name=dataset.name, results=..., duration_s=...)

        Cases are independent, so parallelism is free real estate: 50 cases at
        4-way concurrency turns a coffee break into 12 seconds. Rate limits are the
        only reason to keep the number modest.
        """
        # TODO: implement
        raise NotImplementedError
