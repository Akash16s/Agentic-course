"""EXERCISE 4 — Reflection.

    pytest chapters/ch07_planning/tests -q -k reflection
"""

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
    """acceptable: bool, issues: list[str] = [], suggestion: str = "" """

    acceptable: bool

    @property
    def summary(self) -> str:
        """"acceptable" when acceptable; otherwise the issues joined with "; ",
        falling back to "unspecified problems" if the list is empty."""
        # TODO: implement
        raise NotImplementedError


def json_object(raw: str) -> dict[str, Any] | None:
    """Pull a JSON object out of a model response. None on failure, never raises.

    Same shape as Exercise 2's `json_array` but for `{...}`.
    """
    # TODO: implement
    raise NotImplementedError


def parse_critique(raw: str) -> Critique:
    """Parse a critic response.

    Spec:
      * unparseable -> Critique(acceptable=True)        <- FAIL OPEN
      * issues = the non-empty strings in obj["issues"]
      * acceptable = bool(obj.get("acceptable", not issues)) AND there are no issues
        (a critic that says acceptable=true and then lists three problems has
         contradicted itself; believe the problems)
      * suggestion = str(obj.get("suggestion", ""))

    WHY FAIL OPEN: if a broken critic meant "rejected", one malformed response sends
    the agent into an endless revision loop. Expensive, and invisible — every round
    looks like progress. Failing open costs you exactly one missed review.
    """
    # TODO: implement
    raise NotImplementedError


def reflect_loop(
    task: str,
    produce: Callable[[str | None], str],
    criticise: Callable[[str, str], Critique],
    *,
    max_rounds: int = 3,
) -> tuple[str, list[Critique]]:
    """Produce, critique, revise. Return (final answer, all critiques).

    Spec:
      answer = produce(None)
      repeat up to max_rounds:
          critique = criticise(task, answer)
          record it
          if critique.acceptable: stop
          answer = produce(critique.suggestion or critique.summary)
      return answer, critiques

    Note `produce` takes the feedback, not the previous answer — the closure the
    caller passes already holds whatever context it needs. Keeping the interface
    narrow is what lets you test this with two three-line lambdas.

    BEFORE YOU SHIP THIS ANYWHERE: reflection helps only when the critic can check
    something the producer could not (a compiler, a schema, the sources, a
    checklist). A critic with identical information generates plausible objections
    on demand and you pay 2-3x for a reworded answer. Chapter 10 shows you how to
    measure which one you have.
    """
    # TODO: implement
    raise NotImplementedError
