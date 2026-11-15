"""EXERCISE 2 — Checks.

A Check is `Callable[[output, case], CheckResult]`. Each function here is a FACTORY
that returns one — `contains("Paris")` gives you a check you can put in a list.

    pytest chapters/ch10_evals_basics/tests -q -k checks
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from .exercise_1_dataset import EvalCase


@dataclass
class CheckResult:
    """name: str, passed: bool, detail: str = "", score: float | None = None

    `detail` is only set on FAILURE, and it should say what was expected and what
    happened. A report full of "failed" tells you nothing.

    `score` stays None here; Chapter 11's graded checks use it.
    """

    name: str
    passed: bool
    detail: str = ""
    score: float | None = None


Check = Callable[[Any, EvalCase], CheckResult]


def text_of(output: Any) -> str:
    """Get comparable text from either a bare string or an AgentResult.

    Spec: a str passes through; anything else -> str(getattr(output, "output", output))
    with None becoming "".

    This one helper is why every check works with both a plain string agent and a
    full AgentResult, and why the tests can use strings.
    """
    # TODO: implement
    raise NotImplementedError


def contains(needle: str, *, case_sensitive: bool = False) -> Check:
    """Output must contain `needle`. name = "contains"."""
    # TODO: implement
    raise NotImplementedError


def not_contains(needle: str, *, case_sensitive: bool = False) -> Check:
    """Output must NOT contain `needle`. name = "not_contains"."""
    # TODO: implement
    raise NotImplementedError


def matches(pattern: str, *, flags: int = re.IGNORECASE) -> Check:
    """Output must match a regex (`search`, not `match`). name = "matches"."""
    # TODO: implement
    raise NotImplementedError


def equals_expected(*, normalise: Callable[[str], str] | None = None) -> Check:
    """Output must equal `case.expected`. name = "equals_expected".

    `normalise` defaults to `lambda s: s.strip().lower()`.

    NORMALISE BY DEFAULT. Without it a third of your failures are trailing
    whitespace and differing capitalisation, and a suite whose failures are mostly
    noise is a suite people stop reading — which is worse than no suite, because
    now the real failures are ignored too.
    """
    # TODO: implement
    raise NotImplementedError


def expected_contains() -> Check:
    """Every string in `case.expected` must appear in the output.

    `expected` may be a single string or a list. name = "expected_contains".
    On failure, report ALL the missing ones, not just the first.
    """
    # TODO: implement
    raise NotImplementedError


# ------------------------------------------------- trajectory checks
# These need an AgentResult (Chapter 3). They catch failures that output checks
# cannot see: the right answer reached the wrong way.


def tool_called(name: str) -> Check:
    """`name` appears in `output.tool_sequence`. name = "tool_called".

    Use `getattr(output, "tool_sequence", []) or []` so a plain-string output
    fails cleanly rather than raising.

    On failure, include the sequence that DID happen — "search never called; got
    ['read_file', 'read_file']" tells you what to fix.
    """
    # TODO: implement
    raise NotImplementedError


def tool_not_called(name: str) -> Check:
    """`name` must NOT appear. name = "tool_not_called".

    Put `tool_not_called("delete_user")` on every case in a suite that has a
    destructive tool. It costs nothing and it is exactly the check you will wish
    you had written.
    """
    # TODO: implement
    raise NotImplementedError


def max_steps(limit: int) -> Check:
    """`output.step_count <= limit`. name = "max_steps".

    Catches the agent that gets the right answer after eleven tool calls. The
    output looks perfect and the agent is broken.
    """
    # TODO: implement
    raise NotImplementedError


def max_cost(limit_usd: float) -> Check:
    """`output.cost <= limit_usd`. name = "max_cost"."""
    # TODO: implement
    raise NotImplementedError


def succeeded() -> Check:
    """`output.succeeded` is True. name = "succeeded".

    On failure include the stop reason:
    `getattr(getattr(output, "stop_reason", None), "value", "unknown")`.
    """
    # TODO: implement
    raise NotImplementedError


def custom(name: str, fn: Callable[[Any, EvalCase], bool], *, detail: str = "") -> Check:
    """Wrap an arbitrary predicate.

    IF `fn` RAISES, return a FAILED CheckResult naming the exception. A broken
    check is a failed check, never a failed run — otherwise one typo in one custom
    check costs you the whole suite.
    """
    # TODO: implement
    raise NotImplementedError
