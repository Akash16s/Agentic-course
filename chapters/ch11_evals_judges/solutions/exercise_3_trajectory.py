"""SOLUTION — Chapter 11, Exercise 3."""

from __future__ import annotations

from typing import Any, Sequence

from agentlib.evals.core import Check, CheckResult, EvalCase


def tools_of(output: Any) -> list[str]:
    return list(getattr(output, "tool_sequence", []) or [])


def trajectory_exact(expected: Sequence[str]) -> Check:
    """The tool sequence must match exactly. Strict, and usually too strict —
    most tasks have several correct orders."""
    wanted = list(expected)

    def check(output: Any, case: EvalCase) -> CheckResult:
        got = tools_of(output)
        ok = got == wanted
        return CheckResult("trajectory_exact", ok, "" if ok else f"{got} != {wanted}")
    return check


def is_subsequence(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    """Does `needle` appear in order within `haystack`, gaps allowed?"""
    iterator = iter(haystack)
    return all(item in iterator for item in needle)


def trajectory_contains(expected: Sequence[str]) -> Check:
    """These tools must appear, IN THIS ORDER, with anything allowed in between.

    Almost always the right trajectory check. "It looked something up before it
    answered" is what you care about; whether it also listed a directory first is
    not.
    """
    wanted = list(expected)

    def check(output: Any, case: EvalCase) -> CheckResult:
        got = tools_of(output)
        ok = is_subsequence(wanted, got)
        return CheckResult("trajectory_contains", ok,
                           "" if ok else f"{wanted} not a subsequence of {got}")
    return check


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    """Edit distance between two tool sequences.

    A graded alternative to pass/fail: "one tool off" is meaningfully different
    from "completely different plan", and a binary check throws that away.
    """
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, item_a in enumerate(a, start=1):
        current = [i]
        for j, item_b in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,                                # deletion
                current[j - 1] + 1,                             # insertion
                previous[j - 1] + (item_a != item_b),           # substitution
            ))
        previous = current
    return previous[-1]


def trajectory_similarity(expected: Sequence[str]) -> Check:
    """Graded trajectory score in [0, 1] = 1 - distance / max(len).

    Reports a `score`; passes when the sequences match exactly. Use it when you
    want a trend line rather than a gate.
    """
    wanted = list(expected)

    def check(output: Any, case: EvalCase) -> CheckResult:
        got = tools_of(output)
        longest = max(len(wanted), len(got)) or 1
        score = 1.0 - levenshtein(wanted, got) / longest
        return CheckResult("trajectory_similarity", score == 1.0,
                           f"{score:.2f} similar; got {got}", score=score)
    return check
