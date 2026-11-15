"""SOLUTION — Chapter 10, Exercise 3."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .exercise_1_dataset import EvalCase
from .exercise_2_checks import CheckResult, text_of


@dataclass
class CaseResult:
    case: EvalCase
    checks: list[CheckResult] = field(default_factory=list)
    output: Any = None
    error: str | None = None
    duration_s: float = 0.0
    cost: float = 0.0

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


@dataclass
class EvalReport:
    name: str
    results: list[CaseResult] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def errored(self) -> int:
        return sum(1 for r in self.results if r.error is not None)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self.results)

    @property
    def p50_duration(self) -> float:
        durations = [r.duration_s for r in self.results]
        return statistics.median(durations) if durations else 0.0

    def failures_by_check(self) -> dict[str, int]:
        """Which CHECK fails most often. The most actionable number in the report:
        it points at what to fix, where a pass rate only says something is wrong."""
        counts: dict[str, int] = {}
        for result in self.results:
            for check in result.failures:
                counts[check.name] = counts.get(check.name, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def meets(self, threshold: float) -> bool:
        return self.pass_rate >= threshold

    def summary(self) -> str:
        lines = [
            f"{self.name}: {self.passed}/{self.total} passed "
            f"({self.pass_rate:.0%})  ${self.total_cost:.4f}  "
            f"{self.duration_s:.1f}s  p50 {self.p50_duration:.2f}s"
        ]
        if self.errored:
            lines.append(f"  {self.errored} case(s) errored")
        by_check = self.failures_by_check()
        if by_check:
            lines.append("  failures by check: " + ", ".join(
                f"{name} x{n}" for name, n in by_check.items()))
        return "\n".join(lines)

    def failure_detail(self, limit: int = 10) -> str:
        lines = []
        for result in self.results:
            if result.passed:
                continue
            lines.append(f"\n[{result.case.id}] {result.case.input[:70]}")
            if result.error:
                lines.append(f"    ERROR: {result.error}")
            for check in result.failures:
                lines.append(f"    x {check.name}: {check.detail}")
            lines.append(f"    got: {text_of(result.output)[:160]}")
            if len(lines) > limit * 4:
                lines.append("\n  ... (truncated)")
                break
        return "\n".join(lines)
