"""SOLUTION — Chapter 9, Exercise 4."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuardResult:
    """A guard's verdict. `value` may be a MODIFIED version of the input."""

    passed: bool
    value: Any
    reason: str = ""


class Guardrail:
    """Base class. A guard inspects, and may rewrite, a value."""

    name = "guardrail"

    def check(self, value: Any) -> GuardResult:  # pragma: no cover - interface
        raise NotImplementedError


class MaxLength(Guardrail):
    """Reject or truncate over-long output."""

    name = "max_length"

    def __init__(self, limit: int, *, truncate: bool = False) -> None:
        self.limit = limit
        self.truncate = truncate

    def check(self, value: Any) -> GuardResult:
        text = str(value)
        if len(text) <= self.limit:
            return GuardResult(True, value)
        if self.truncate:
            return GuardResult(True, text[: self.limit], "truncated")
        return GuardResult(False, value, f"output is {len(text)} chars, limit {self.limit}")


class Blocklist(Guardrail):
    """Reject output containing any forbidden term (case-insensitive)."""

    name = "blocklist"

    def __init__(self, terms: list[str]) -> None:
        self.terms = [t.lower() for t in terms]

    def check(self, value: Any) -> GuardResult:
        text = str(value).lower()
        hits = [t for t in self.terms if t in text]
        if hits:
            return GuardResult(False, value, f"contains blocked terms: {hits}")
        return GuardResult(True, value)


#: Deliberately conservative patterns. Real PII detection needs a proper library;
#: these catch the obvious cases and demonstrate the shape.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\+?\d[\d\s().-]{8,}\d"),
}


class RedactPII(Guardrail):
    """Replace obvious PII with placeholders. Always passes; rewrites the value."""

    name = "redact_pii"

    def __init__(self, kinds: list[str] | None = None) -> None:
        self.kinds = kinds or list(PII_PATTERNS)

    def check(self, value: Any) -> GuardResult:
        text = str(value)
        found: list[str] = []
        for kind in self.kinds:
            pattern = PII_PATTERNS.get(kind)
            if pattern is None:
                continue
            text, n = pattern.subn(f"[{kind.upper()}]", text)
            if n:
                found.append(f"{kind} x{n}")
        return GuardResult(True, text, f"redacted: {', '.join(found)}" if found else "")


@dataclass
class GuardrailReport:
    value: Any
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def run_guardrails(value: Any, guards: list[Guardrail]) -> GuardrailReport:
    """Run guards IN ORDER, each seeing the previous one's output.

    Order matters and is a design decision: put rewriting guards (redaction) before
    rejecting guards (blocklist), or you reject text that redaction would have made
    acceptable.

    Runs every guard even after one fails, so the report lists all the problems
    rather than only the first.
    """
    report = GuardrailReport(value=value)
    for guard in guards:
        result = guard.check(report.value)
        report.value = result.value
        if result.reason:
            report.notes.append(f"{guard.name}: {result.reason}")
        if not result.passed:
            report.passed = False
            report.failures.append(f"{guard.name}: {result.reason}")
    return report
