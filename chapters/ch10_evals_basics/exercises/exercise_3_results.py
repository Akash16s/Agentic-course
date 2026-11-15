"""EXERCISE 3 — Results and reporting.

    pytest chapters/ch10_evals_basics/tests -q -k results
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .exercise_1_dataset import EvalCase
from .exercise_2_checks import CheckResult, text_of


@dataclass
class CaseResult:
    """case: EvalCase, checks: list[CheckResult] = [], output: Any = None,
       error: str|None = None, duration_s: float = 0.0, cost: float = 0.0"""

    case: EvalCase
    checks: list[CheckResult] = field(default_factory=list)
    output: Any = None
    error: str | None = None
    duration_s: float = 0.0
    cost: float = 0.0

    @property
    def passed(self) -> bool:
        """No error AND every check passed.

        An errored case is a FAILED case, not a skipped one. Letting errors quietly
        drop out of the denominator is how a suite reports 100% while half of it
        crashed.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def failures(self) -> list[CheckResult]:
        # TODO: implement
        raise NotImplementedError


@dataclass
class EvalReport:
    """name: str, results: list[CaseResult] = [], duration_s: float = 0.0"""

    name: str
    results: list[CaseResult] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def total(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def passed(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def failed(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def errored(self) -> int:
        """Cases where the AGENT raised, as distinct from cases that just failed
        their checks. A rising error count is an infrastructure problem; a rising
        failure count is a quality problem. Different people fix them."""
        # TODO: implement
        raise NotImplementedError

    @property
    def pass_rate(self) -> float:
        """passed/total, or 0.0 for an empty report (no ZeroDivisionError)."""
        # TODO: implement
        raise NotImplementedError

    @property
    def total_cost(self) -> float:
        # TODO: implement
        raise NotImplementedError

    @property
    def p50_duration(self) -> float:
        """Median case duration; 0.0 when empty.

        Median rather than mean: one 40-second outlier should not make the whole
        suite look slow.
        """
        # TODO: implement
        raise NotImplementedError

    def failures_by_check(self) -> dict[str, int]:
        """{check name: how many cases it failed}, most frequent FIRST.

        THE MOST ACTIONABLE LINE IN THE REPORT. A pass rate says something is
        wrong. This says what: "tool_called x6" is a tool-description problem,
        "expected_contains x6" is a prompt problem, and they have different fixes.
        """
        # TODO: implement
        raise NotImplementedError

    def meets(self, threshold: float) -> bool:
        """pass_rate >= threshold. The CI gate."""
        # TODO: implement
        raise NotImplementedError

    def summary(self) -> str:
        """One-to-three line summary. Must include the pass count, the total, the
        percentage, the cost and the duration. Include the errored count when
        non-zero, and the failures_by_check line when non-empty.

        Suggested:
            support-v3: 42/50 passed (84%)  $0.3100  18.4s  p50 0.32s
              failures by check: tool_called x6, max_steps x3
        """
        # TODO: implement
        raise NotImplementedError

    def failure_detail(self, limit: int = 10) -> str:
        """The failing cases, with input, each failed check and the actual output.

        This is what you read after the summary. Include the OUTPUT — a failure you
        cannot see the output of is a failure you have to re-run to understand.
        Truncate; a report is for reading.
        """
        # TODO: implement
        raise NotImplementedError
