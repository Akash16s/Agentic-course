"""EXERCISE 3 — Trajectory evaluation.

    pytest chapters/ch11_evals_judges/tests -q -k trajectory
"""

from __future__ import annotations

from typing import Any, Sequence

from agentlib.evals.core import Check, CheckResult, EvalCase


def tools_of(output: Any) -> list[str]:
    """`output.tool_sequence` as a list, or [] for a plain string."""
    # TODO: implement
    raise NotImplementedError


def is_subsequence(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    """Does `needle` appear IN ORDER within `haystack`, gaps allowed?

    >>> is_subsequence(["a", "c"], ["a", "b", "c"])
    True
    >>> is_subsequence(["c", "a"], ["a", "b", "c"])
    False

    The one-liner worth knowing:
        it = iter(haystack); return all(x in it for x in needle)
    `x in it` consumes the iterator up to the match, so order is enforced for free.
    """
    # TODO: implement
    raise NotImplementedError


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    """Edit distance between two tool sequences (insert/delete/substitute = 1).

    Standard two-row dynamic programme:
        empty a -> len(b); empty b -> len(a)
        previous = list(range(len(b) + 1))
        for i, x in enumerate(a, 1):
            current = [i]
            for j, y in enumerate(b, 1):
                current.append(min(previous[j] + 1,               # delete
                                   current[j-1] + 1,              # insert
                                   previous[j-1] + (x != y)))     # substitute
            previous = current
        return previous[-1]

    Why bother: "one tool off" and "a completely different plan" are very different
    failures, and a boolean check throws that distinction away exactly when you are
    trying to see whether a change helped.
    """
    # TODO: implement
    raise NotImplementedError


def trajectory_exact(expected: Sequence[str]) -> Check:
    """The sequence must match exactly. name = "trajectory_exact".

    Usually TOO STRICT — most tasks have several correct orders, and a suite that
    fails on a valid alternative route trains you to ignore it.
    """
    # TODO: implement
    raise NotImplementedError


def trajectory_contains(expected: Sequence[str]) -> Check:
    """`expected` must be a SUBSEQUENCE of the actual sequence.
    name = "trajectory_contains".

    Your default. "It looked something up before it answered" is what you care
    about; whether it also listed a directory first is not your business.
    """
    # TODO: implement
    raise NotImplementedError


def trajectory_similarity(expected: Sequence[str]) -> Check:
    """Graded score = 1 - levenshtein / max(len(expected), len(got), 1).
    name = "trajectory_similarity".

    `passed` only when the score is exactly 1.0, but SET `score` on the result —
    that is the point of this check. Use it when you want a trend line rather than
    a gate.
    """
    # TODO: implement
    raise NotImplementedError
