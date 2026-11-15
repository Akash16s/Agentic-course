"""The eval harness — finding out whether any of this actually works.

Promoted from Chapter 10.

Everything before this chapter was building. This is the part that tells you whether
a change made the agent better or worse, which is the only way to improve it on
purpose rather than by vibes.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

# ------------------------------------------------------------------ dataset


@dataclass
class EvalCase:
    """One test. `expected` is free-form: whatever your checks need."""

    id: str
    input: str
    expected: Any = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Dataset:
    """A named set of eval cases, loadable from JSONL.

    JSONL rather than JSON: you can append a case without rewriting the file, diff
    it line by line in review, and stream it if it gets big. Eval datasets are
    edited by hand far more often than people expect, and that decides the format.
    """

    def __init__(self, cases: Iterable[EvalCase] = (), *, name: str = "dataset") -> None:
        self.name = name
        self.cases = list(cases)

    def __len__(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def filter(self, *, tag: str | None = None,
               predicate: Callable[[EvalCase], bool] | None = None) -> "Dataset":
        cases = self.cases
        if tag is not None:
            cases = [c for c in cases if tag in c.tags]
        if predicate is not None:
            cases = [c for c in cases if predicate(c)]
        return Dataset(cases, name=f"{self.name}[filtered]")

    @classmethod
    def from_jsonl(cls, path: str, *, name: str | None = None) -> "Dataset":
        cases: list[EvalCase] = []
        with open(path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                row = json.loads(line)
                cases.append(
                    EvalCase(
                        id=str(row.get("id", line_number)),
                        input=row["input"],
                        expected=row.get("expected"),
                        tags=list(row.get("tags", [])),
                        metadata=row.get("metadata", {}),
                    )
                )
        return cls(cases, name=name or path)

    def to_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            for case in self.cases:
                handle.write(json.dumps(asdict(case)) + "\n")


# ------------------------------------------------------------------- checks


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    score: float | None = None   # for graded checks (Chapter 11)


#: A check takes (output, case) and returns a CheckResult.
Check = Callable[[Any, EvalCase], CheckResult]


def text_of(output: Any) -> str:
    """Accept a bare string or anything with `.output` (an AgentResult).

    This one helper is why every check works with both a plain-string agent and a
    full AgentResult — and why the whole eval test-suite can run on strings.
    """
    if isinstance(output, str):
        return output
    return str(getattr(output, "output", output) or "")


def contains(needle: str, *, case_sensitive: bool = False) -> Check:
    def check(output: Any, case: EvalCase) -> CheckResult:
        text = text_of(output)
        hay, target = (text, needle) if case_sensitive else (text.lower(), needle.lower())
        found = target in hay
        return CheckResult("contains", found,
                           "" if found else f"{needle!r} not in output")
    return check


def not_contains(needle: str, *, case_sensitive: bool = False) -> Check:
    def check(output: Any, case: EvalCase) -> CheckResult:
        text = text_of(output)
        hay, target = (text, needle) if case_sensitive else (text.lower(), needle.lower())
        absent = target not in hay
        return CheckResult("not_contains", absent,
                           "" if absent else f"{needle!r} should not appear")
    return check


def matches(pattern: str, *, flags: int = re.IGNORECASE) -> Check:
    compiled = re.compile(pattern, flags)

    def check(output: Any, case: EvalCase) -> CheckResult:
        found = bool(compiled.search(text_of(output)))
        return CheckResult("matches", found,
                           "" if found else f"no match for /{pattern}/")
    return check


def equals_expected(*, normalise: Callable[[str], str] | None = None) -> Check:
    """Compare against `case.expected` exactly.

    `normalise` matters more than it looks: without lowercasing and stripping, half
    your failures are whitespace, and you stop trusting the suite.
    """
    norm = normalise or (lambda s: s.strip().lower())

    def check(output: Any, case: EvalCase) -> CheckResult:
        got, want = norm(text_of(output)), norm(str(case.expected))
        return CheckResult("equals_expected", got == want,
                           "" if got == want else f"expected {want!r}, got {got!r}")
    return check


def expected_contains() -> Check:
    """Every string in `case.expected` (a str or list of str) must appear."""
    def check(output: Any, case: EvalCase) -> CheckResult:
        wanted = case.expected if isinstance(case.expected, list) else [case.expected]
        text = text_of(output).lower()
        missing = [w for w in wanted if str(w).lower() not in text]
        return CheckResult("expected_contains", not missing,
                           "" if not missing else f"missing: {missing}")
    return check


def tool_called(name: str) -> Check:
    """The agent used this tool at least once. Needs an AgentResult."""
    def check(output: Any, case: EvalCase) -> CheckResult:
        sequence = list(getattr(output, "tool_sequence", []) or [])
        used = name in sequence
        return CheckResult("tool_called", used,
                           "" if used else f"{name!r} never called; got {sequence}")
    return check


def tool_not_called(name: str) -> Check:
    def check(output: Any, case: EvalCase) -> CheckResult:
        sequence = list(getattr(output, "tool_sequence", []) or [])
        unused = name not in sequence
        return CheckResult("tool_not_called", unused,
                           "" if unused else f"{name!r} should not have been called")
    return check


def max_steps(limit: int) -> Check:
    def check(output: Any, case: EvalCase) -> CheckResult:
        steps = int(getattr(output, "step_count", 0) or 0)
        return CheckResult("max_steps", steps <= limit,
                           "" if steps <= limit else f"{steps} steps > {limit}")
    return check


def max_cost(limit_usd: float) -> Check:
    def check(output: Any, case: EvalCase) -> CheckResult:
        cost = float(getattr(output, "cost", 0.0) or 0.0)
        return CheckResult("max_cost", cost <= limit_usd,
                           "" if cost <= limit_usd else f"${cost:.4f} > ${limit_usd:.4f}")
    return check


def succeeded() -> Check:
    """The agent stopped for a good reason, not max_steps/budget/timeout."""
    def check(output: Any, case: EvalCase) -> CheckResult:
        ok = bool(getattr(output, "succeeded", True))
        reason = getattr(getattr(output, "stop_reason", None), "value", "unknown")
        return CheckResult("succeeded", ok, "" if ok else f"stopped: {reason}")
    return check


def custom(name: str, fn: Callable[[Any, EvalCase], bool], *, detail: str = "") -> Check:
    def check(output: Any, case: EvalCase) -> CheckResult:
        try:
            passed = bool(fn(output, case))
        except Exception as exc:  # noqa: BLE001 - a broken check is a failed check
            return CheckResult(name, False, f"check raised: {type(exc).__name__}: {exc}")
        return CheckResult(name, passed, "" if passed else detail)
    return check


# ------------------------------------------------------------------ results


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


# ------------------------------------------------------------------- runner


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
