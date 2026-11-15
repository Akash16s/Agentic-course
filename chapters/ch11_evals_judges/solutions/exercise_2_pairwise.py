"""SOLUTION — Chapter 11, Exercise 2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


def json_object(raw: str) -> dict[str, Any] | None:
    raw = (raw or "").strip()
    if "```" in raw:
        raw = max(raw.split("```"), key=len).removeprefix("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start: end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
    winner: str          # "a", "b" or "tie" — refers to the ORIGINAL arguments
    reasoning: str = ""
    swapped_agreement: bool | None = None  # None when only one order was tried


def pairwise_compare(
    task: str,
    answer_a: str,
    answer_b: str,
    rubric: str,
    call_model: Callable[[str], str],
    *,
    control_position_bias: bool = True,
) -> Comparison:
    """Which answer is better? Optionally judged in both orders.

    POSITION BIAS IS REAL AND LARGE. Models prefer whichever answer they see first
    (sometimes second, depending on the model) by a wide margin — enough to reverse
    a genuine quality difference. Judging A-vs-B and B-vs-A and requiring agreement
    turns that bias into an honest "tie".

    It costs two calls instead of one. Pay it: a pairwise eval without position
    control is measuring the judge's layout preference, not your agent.
    """
    first = ask_pairwise(task, answer_a, answer_b, rubric, call_model)
    if not control_position_bias:
        return Comparison(winner=first[0], reasoning=first[1])

    # same comparison, reversed; flip the answer back to the original labelling
    second_raw = ask_pairwise(task, answer_b, answer_a, rubric, call_model)
    flip = {"a": "b", "b": "a", "tie": "tie"}
    second = (flip[second_raw[0]], second_raw[1])

    if first[0] == second[0]:
        return Comparison(winner=first[0], reasoning=first[1], swapped_agreement=True)
    return Comparison(
        winner="tie",
        reasoning=f"order-dependent: {first[0]} then {second[0]} — treating as a tie",
        swapped_agreement=False,
    )


def ask_pairwise(task, a, b, rubric, call_model) -> tuple[str, str]:
    raw = call_model(PAIRWISE_PROMPT.format(task=task, a=a, b=b, rubric=rubric))
    obj = json_object(raw) or {}
    winner = str(obj.get("winner", "")).strip().lower()
    if winner not in ("a", "b", "tie"):
        winner = "tie"
    return winner, str(obj.get("reasoning", ""))
