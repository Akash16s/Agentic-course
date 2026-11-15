"""EXERCISE 4 — Guardrails.

    pytest chapters/ch09_structured_output/tests -q -k guardrails
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuardResult:
    """passed: bool, value: Any, reason: str = ""

    `value` may be a MODIFIED version of the input — a guard can rewrite as well as
    reject, which is what makes redaction a guard rather than a separate concept.
    """

    passed: bool
    value: Any


class Guardrail:
    """Base class. Subclasses set `name` and implement `check`."""

    name = "guardrail"

    def check(self, value: Any) -> GuardResult:
        raise NotImplementedError


class MaxLength(Guardrail):
    """__init__(self, limit: int, *, truncate: bool = False)

    name = "max_length"

    check:
      * within the limit        -> GuardResult(True, value)
      * over, truncate=True     -> GuardResult(True, text[:limit], "truncated")
      * over, truncate=False    -> GuardResult(False, value,
                                     f"output is {n} chars, limit {limit}")

    Measure `str(value)` so this works on non-strings too.
    """

    name = "max_length"

    def __init__(self, limit: int, *, truncate: bool = False) -> None:
        # TODO: implement
        raise NotImplementedError

    def check(self, value: Any) -> GuardResult:
        # TODO: implement
        raise NotImplementedError


class Blocklist(Guardrail):
    """Reject output containing any forbidden term, case-insensitively.

    name = "blocklist"
    Reason on failure: f"contains blocked terms: {hits}" where `hits` is the list
    of matched terms — plural, because listing only the first means fixing them one
    at a time.
    """

    name = "blocklist"

    def __init__(self, terms: list[str]) -> None:
        # TODO: implement
        raise NotImplementedError

    def check(self, value: Any) -> GuardResult:
        # TODO: implement
        raise NotImplementedError


#: Deliberately conservative. Real PII detection needs a proper library; these catch
#: the obvious cases and show the shape.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\+?\d[\d\s().-]{8,}\d"),
}


class RedactPII(Guardrail):
    """Replace obvious PII with placeholders. ALWAYS PASSES; rewrites the value.

    name = "redact_pii"
    __init__(self, kinds: list[str] | None = None)  — defaults to all of PII_PATTERNS

    check:
      * for each kind, `pattern.subn(f"[{kind.upper()}]", text)`
      * record which kinds matched and how many, e.g. "email x2"
      * return GuardResult(True, redacted_text, "redacted: email x2, phone x1")
        or GuardResult(True, text, "") when nothing matched
      * skip unknown kind names rather than raising

    Passing rather than rejecting is deliberate: the point is to make the output
    safe, not to withhold it.
    """

    name = "redact_pii"

    def __init__(self, kinds: list[str] | None = None) -> None:
        # TODO: implement
        raise NotImplementedError

    def check(self, value: Any) -> GuardResult:
        # TODO: implement
        raise NotImplementedError


@dataclass
class GuardrailReport:
    """value: Any, passed: bool = True, failures: list[str] = [], notes: list[str] = []"""

    value: Any


def run_guardrails(value: Any, guards: list[Guardrail]) -> GuardrailReport:
    """Run guards IN ORDER, each seeing the PREVIOUS one's output value.

    Spec:
      * thread the value through: report.value = result.value after every guard
      * any non-empty reason -> append f"{guard.name}: {reason}" to `notes`
      * a failure -> passed = False, and append the same string to `failures`
      * RUN EVERY GUARD EVEN AFTER ONE FAILS, so the report lists all the problems

    ORDER IS A DESIGN DECISION, NOT AN IMPLEMENTATION DETAIL. Rewriting guards
    (redaction) must run BEFORE rejecting guards (blocklist), or you reject text
    that redaction would have made acceptable — and the user gets an error where
    they should have got an answer.
    """
    # TODO: implement
    raise NotImplementedError
