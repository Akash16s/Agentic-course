"""SOLUTION — Chapter 7, Exercise 4."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


CRITIC_PROMPT = """\
You are reviewing another assistant's work. Be specific and be hard to please, but do
not invent problems.

TASK: {task}

ANSWER:
{answer}

Judge only these:
1. Does it actually answer the task that was asked?
2. Is anything stated as fact that was not established by the work done?
3. Is anything required by the task missing?

Return ONLY JSON:
{{"acceptable": true/false, "issues": ["..."], "suggestion": "one concrete fix"}}

If it is acceptable, return an empty issues list. Do not pad."""


@dataclass
class Critique:
    acceptable: bool
    issues: list[str] = field(default_factory=list)
    suggestion: str = ""

    @property
    def summary(self) -> str:
        if self.acceptable:
            return "acceptable"
        return "; ".join(self.issues) or "unspecified problems"


def parse_critique(raw: str) -> Critique:
    """Parse a critic response. Unparseable output is treated as ACCEPTABLE.

    That default matters: if a broken critic meant "rejected", one malformed response
    would send the agent into an endless revision loop, which is both expensive and
    invisible. Failing open costs you one missed review.
    """
    obj = json_object(raw)
    if obj is None:
        return Critique(acceptable=True)
    issues = [str(i) for i in (obj.get("issues") or []) if str(i).strip()]
    acceptable = bool(obj.get("acceptable", not issues))
    return Critique(
        acceptable=acceptable and not issues,
        issues=issues,
        suggestion=str(obj.get("suggestion", "")),
    )


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


def reflect_loop(
    task: str,
    produce: Callable[[str | None], str],
    criticise: Callable[[str, str], Critique],
    *,
    max_rounds: int = 3,
) -> tuple[str, list[Critique]]:
    """Produce, critique, revise — up to `max_rounds` times.

    `produce(feedback)` is called with None first, then with the critic's suggestion.
    Returns the final answer and every critique made along the way.

    WHEN THIS HELPS: verifiable work — code that must compile, output that must match
    a format, answers that must cite sources.

    WHEN IT DOES NOT: matters of taste, and anything the critic cannot actually check.
    A critic with no more information than the producer mostly generates plausible
    objections, and you pay 2-3x for a differently-worded answer. Measure it
    (Chapter 10) rather than assuming it helps.
    """
    critiques: list[Critique] = []
    answer = produce(None)
    for _ in range(max_rounds):
        critique = criticise(task, answer)
        critiques.append(critique)
        if critique.acceptable:
            break
        answer = produce(critique.suggestion or critique.summary)
    return answer, critiques
