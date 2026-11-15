"""EXERCISE 2 — Pairwise comparison, with position-bias control.

    pytest chapters/ch11_evals_judges/tests -q -k pairwise
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

PAIRWISE_PROMPT = """\
Two assistants answered the same task. Decide which answer is better.

TASK:
{task}

ANSWER A:
{a}

ANSWER B:
{b}

CRITERIA:
{rubric}

Ignore length and formatting unless the criteria mention them. Judge the substance.

Return ONLY JSON: {{"winner": "A" | "B" | "tie", "reasoning": "one sentence"}}"""


@dataclass
class Comparison:
    """winner: str ("a"/"b"/"tie", referring to the ORIGINAL arguments),
       reasoning: str = "", swapped_agreement: bool | None = None

    `swapped_agreement` is None when only one order was tried.
    """

    winner: str


def json_object(raw: str) -> dict[str, Any] | None:
    """Same helper as Chapter 9/7: pull a {...} out of a model response, or None."""
    # TODO: implement
    raise NotImplementedError


def ask_pairwise(task, a, b, rubric, call_model) -> tuple[str, str]:
    """One comparison. Returns (winner, reasoning) with winner in {"a","b","tie"}.

    Anything unrecognised becomes "tie" — a judge that produced garbage has not
    expressed a preference, and inventing one would be worse than admitting it.
    """
    # TODO: implement
    raise NotImplementedError


def pairwise_compare(
    task: str,
    answer_a: str,
    answer_b: str,
    rubric: str,
    call_model: Callable[[str], str],
    *,
    control_position_bias: bool = True,
) -> Comparison:
    """Which answer is better? Judged in BOTH orders by default.

    Spec:
      1. first = ask_pairwise(task, answer_a, answer_b, ...)
      2. not controlling for bias -> Comparison(winner=first[0], reasoning=first[1])
      3. second_raw = ask_pairwise(task, answer_b, answer_a, ...)   <- swapped!
         flip its answer back to the original labelling:
             {"a": "b", "b": "a", "tie": "tie"}
      4. the two agree -> Comparison(winner, reasoning=first[1],
                                     swapped_agreement=True)
      5. they disagree -> Comparison("tie", reasoning explaining the order
                                     dependence, swapped_agreement=False)

    POSITION BIAS IS REAL AND LARGE. Models prefer whichever answer they see first
    (some prefer the second — it varies), by a margin big enough to REVERSE a
    genuine quality difference. A judge that always answers "A" is not comparing
    anything, and without this control you would record a clean win.

    Two calls instead of one. Pay it. A pairwise eval without position control
    measures the judge's layout preference, not your agent.

    Useful side effect: the disagreement rate across a suite IS your noise floor.
    If the orders disagree 40% of the time, the rubric is not discriminating and no
    sample size will rescue it.
    """
    # TODO: implement
    raise NotImplementedError
