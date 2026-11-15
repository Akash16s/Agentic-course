"""SOLUTION — Chapter 10, Exercise 2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from .exercise_1_dataset import EvalCase


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    score: float | None = None   # for graded checks (Chapter 11)


#: A check takes (output, case) and returns a CheckResult.
Check = Callable[[Any, EvalCase], CheckResult]


def text_of(output: Any) -> str:
    """Accept a bare string or anything with `.output` (an AgentResult)."""
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
