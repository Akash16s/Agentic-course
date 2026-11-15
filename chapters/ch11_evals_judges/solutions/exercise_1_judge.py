"""SOLUTION — Chapter 11, Exercise 1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from agentlib.evals.core import Check, CheckResult, EvalCase, text_of


JUDGE_PROMPT = """\
You are grading one response against a rubric. Be strict and be consistent.

TASK GIVEN TO THE ASSISTANT:
{task}

RESPONSE TO GRADE:
{response}
{reference}
RUBRIC:
{rubric}

Work through the rubric criteria one at a time, then give a score.

Return ONLY JSON:
{{"reasoning": "one sentence per criterion", "score": <{low}-{high}>, "passed": true/false}}"""

REFERENCE_BLOCK = """
REFERENCE ANSWER (a known-good response; the response above need not match it word
for word, but should not contradict it):
{reference}
"""


@dataclass
class Judgement:
    score: float
    passed: bool
    reasoning: str = ""
    raw: str = ""


class LLMJudge:
    """Grade free-form output with a model and a rubric.

    >>> judge = LLMJudge(rubric="1. Factually correct\\n2. Under 50 words",
    ...                  call_model=my_cheap_model)
    >>> judge.grade("summarise X", "X is ...").score
    4.0
    """

    def __init__(
        self,
        rubric: str,
        call_model: Callable[[str], str],
        *,
        scale: tuple[int, int] = (1, 5),
        pass_at: float | None = None,
    ) -> None:
        if not rubric.strip():
            raise ValueError("a judge without a rubric is a coin flip with extra steps")
        self.rubric = rubric.strip()
        self.call_model = call_model
        self.low, self.high = scale
        # default: pass at 80% of the scale
        self.pass_at = pass_at if pass_at is not None else self.low + 0.8 * (
            self.high - self.low
        )

    def prompt(self, task: str, response: str, reference: str | None = None) -> str:
        return JUDGE_PROMPT.format(
            task=task,
            response=response,
            reference=REFERENCE_BLOCK.format(reference=reference) if reference else "",
            rubric=self.rubric,
            low=self.low,
            high=self.high,
        )

    def grade(self, task: str, response: str, reference: str | None = None) -> Judgement:
        raw = self.call_model(self.prompt(task, response, reference))
        return self.parse(raw)

    def parse(self, raw: str) -> Judgement:
        """Parse a judgement. Unparseable output scores the MINIMUM and fails.

        The opposite of Chapter 7's critic, deliberately. A critic that fails open
        costs you one skipped review; a JUDGE that fails open silently inflates your
        eval scores, and you will make decisions on those numbers for months.
        Grading failures must be visible.
        """
        obj = _json_object(raw)
        if obj is None:
            # last resort: a bare number somewhere in the text
            match = re.search(r"\b(\d+(?:\.\d+)?)\b", raw or "")
            if match:
                score = _clamp(float(match.group(1)), self.low, self.high)
                return Judgement(score, score >= self.pass_at,
                                 "parsed from unstructured output", raw or "")
            return Judgement(float(self.low), False, "unparseable judgement", raw or "")

        try:
            score = _clamp(float(obj.get("score", self.low)), self.low, self.high)
        except (TypeError, ValueError):
            score = float(self.low)

        passed = obj.get("passed")
        if not isinstance(passed, bool):
            passed = score >= self.pass_at

        return Judgement(score, bool(passed), str(obj.get("reasoning", "")), raw or "")

    def as_check(self, *, name: str = "judge",
                 reference_from_case: bool = True) -> Check:
        """Wrap this judge as a Chapter 10 Check, so it drops into the same runner."""
        def check(output: Any, case: EvalCase) -> CheckResult:
            reference = str(case.expected) if (reference_from_case and case.expected) else None
            judgement = self.grade(case.input, text_of(output), reference)
            return CheckResult(
                name=name,
                passed=judgement.passed,
                detail="" if judgement.passed
                       else f"scored {judgement.score}: {judgement.reasoning[:200]}",
                score=judgement.score,
            )
        return check


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _json_object(raw: str) -> dict[str, Any] | None:
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
