"""EXERCISE 1 — LLM-as-judge.

    pytest chapters/ch11_evals_judges/tests -q -k judge
"""

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
    """score: float, passed: bool, reasoning: str = "", raw: str = "" """

    score: float
    passed: bool


class LLMJudge:
    """Grade free-form output with a model and a rubric.

    __init__(self, rubric, call_model, *, scale=(1,5), pass_at=None)

      * an empty rubric -> ValueError. A judge without a rubric is a coin flip with
        extra steps, and it will still confidently produce numbers.
      * store scale as self.low / self.high
      * pass_at defaults to 80% of the way up the scale:
            self.low + 0.8 * (self.high - self.low)
    """

    def __init__(
        self,
        rubric: str,
        call_model: Callable[[str], str],
        *,
        scale: tuple[int, int] = (1, 5),
        pass_at: float | None = None,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def prompt(self, task: str, response: str, reference: str | None = None) -> str:
        """Fill JUDGE_PROMPT. Include REFERENCE_BLOCK only when `reference` is given.

        Note the order in the requested JSON: REASONING FIRST, then score. That is
        chain-of-thought, and swapping them measurably degrades consistency —
        the model commits to a number and then rationalises it.
        """
        # TODO: implement
        raise NotImplementedError

    def grade(self, task: str, response: str, reference: str | None = None) -> Judgement:
        """prompt -> call_model -> parse."""
        # TODO: implement
        raise NotImplementedError

    def parse(self, raw: str) -> Judgement:
        """Parse a judgement. FAILS CLOSED.

        Spec, in order:
          1. try to extract a JSON object (fences, prose either side)
          2. no object -> look for the first bare number in the text:
               found     -> Judgement(clamped, score >= pass_at,
                                      "parsed from unstructured output", raw)
               not found -> Judgement(self.low, False, "unparseable judgement", raw)
          3. with an object:
               score  = clamp(float(obj["score"]), low, high); unparseable -> low
               passed = obj["passed"] if it is a real bool, else score >= pass_at
               reasoning = str(obj.get("reasoning", ""))

        FAIL CLOSED — the minimum score and passed=False. This is the OPPOSITE of
        Chapter 7's critic, deliberately. A critic that fails open costs you one
        skipped review. A judge that fails open silently INFLATES your eval scores,
        and you will make decisions on those numbers for months without knowing.
        """
        # TODO: implement
        raise NotImplementedError

    def as_check(self, *, name: str = "judge",
                 reference_from_case: bool = True) -> Check:
        """Wrap this judge as a Chapter 10 Check, so it drops into the same runner.

        Use `text_of(output)` for the response, `case.input` for the task, and
        `str(case.expected)` as the reference when `reference_from_case` and there
        is one.

        Set `score` on the CheckResult — a graded number is worth much more than a
        boolean when you are looking for a trend.
        """
        # TODO: implement
        raise NotImplementedError
