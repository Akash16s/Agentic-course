"""Grading the things you cannot assert on.

Promoted from Chapter 11.

Chapter 10's checks answer "does the output contain 'Paris'?". This answers "is the
summary any good?" — and, just as importantly, tells you how much to believe the
answer.
"""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from agentlib.evals.core import Check, CheckResult, EvalCase, EvalReport, text_of

# -------------------------------------------------------------- LLM as judge

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


# ----------------------------------------------------------------- pairwise

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
    first = _ask_pairwise(task, answer_a, answer_b, rubric, call_model)
    if not control_position_bias:
        return Comparison(winner=first[0], reasoning=first[1])

    # same comparison, reversed; flip the answer back to the original labelling
    second_raw = _ask_pairwise(task, answer_b, answer_a, rubric, call_model)
    flip = {"a": "b", "b": "a", "tie": "tie"}
    second = (flip[second_raw[0]], second_raw[1])

    if first[0] == second[0]:
        return Comparison(winner=first[0], reasoning=first[1], swapped_agreement=True)
    return Comparison(
        winner="tie",
        reasoning=f"order-dependent: {first[0]} then {second[0]} — treating as a tie",
        swapped_agreement=False,
    )


def _ask_pairwise(task, a, b, rubric, call_model) -> tuple[str, str]:
    raw = call_model(PAIRWISE_PROMPT.format(task=task, a=a, b=b, rubric=rubric))
    obj = _json_object(raw) or {}
    winner = str(obj.get("winner", "")).strip().lower()
    if winner not in ("a", "b", "tie"):
        winner = "tie"
    return winner, str(obj.get("reasoning", ""))


# --------------------------------------------------------------- trajectory


def trajectory_exact(expected: Sequence[str]) -> Check:
    """The tool sequence must match exactly. Strict, and usually too strict —
    most tasks have several correct orders."""
    wanted = list(expected)

    def check(output: Any, case: EvalCase) -> CheckResult:
        got = list(getattr(output, "tool_sequence", []) or [])
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
        got = list(getattr(output, "tool_sequence", []) or [])
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
        got = list(getattr(output, "tool_sequence", []) or [])
        longest = max(len(wanted), len(got)) or 1
        score = 1.0 - levenshtein(wanted, got) / longest
        return CheckResult("trajectory_similarity", score == 1.0,
                           f"{score:.2f} similar; got {got}", score=score)
    return check


# --------------------------------------------------------------- statistics


def bootstrap_ci(
    successes: int,
    total: int,
    *,
    confidence: float = 0.95,
    iterations: int = 2_000,
    rng: random.Random | None = None,
) -> tuple[float, float]:
    """Confidence interval for a pass rate, by resampling.

    Why you need this: 42/50 is 84%, and the 95% interval is roughly 74%-94%. A
    "improvement" from 84% to 88% on 50 cases is well inside the noise. People ship
    changes on differences like that constantly, and revert them a month later
    having learned nothing.
    """
    if total <= 0:
        return (0.0, 0.0)
    rng = rng or random.Random(0)
    observations = [1] * successes + [0] * (total - successes)
    means = []
    for _ in range(iterations):
        sample = [observations[rng.randrange(total)] for _ in range(total)]
        means.append(sum(sample) / total)
    means.sort()
    tail = (1 - confidence) / 2
    return (means[int(tail * iterations)], means[int((1 - tail) * iterations) - 1])


@dataclass
class Comparison2:
    """The result of comparing two eval runs on the same dataset."""

    baseline_rate: float
    candidate_rate: float
    delta: float
    improved: list[str] = field(default_factory=list)   # case ids
    regressed: list[str] = field(default_factory=list)
    significant: bool = False
    note: str = ""


def compare_runs(baseline: EvalReport, candidate: EvalReport,
                 *, min_flips: int = 5) -> Comparison2:
    """Compare two runs CASE BY CASE, not just by headline rate.

    Pass rates hide churn: 42/50 -> 42/50 looks like nothing changed, when six
    cases may have broken and six others fixed. That is not "no change", that is an
    unstable agent, and it is the single most useful thing this function surfaces.

    The significance rule is a deliberately crude stand-in for McNemar's test: a
    difference counts only when the two flip counts differ by at least `min_flips`.
    Crude beats absent; if you want the real test, scipy has it.
    """
    baseline_by_id = {r.case.id: r.passed for r in baseline.results}
    candidate_by_id = {r.case.id: r.passed for r in candidate.results}
    shared = set(baseline_by_id) & set(candidate_by_id)

    improved = sorted(i for i in shared if candidate_by_id[i] and not baseline_by_id[i])
    regressed = sorted(i for i in shared if baseline_by_id[i] and not candidate_by_id[i])

    delta = candidate.pass_rate - baseline.pass_rate
    significant = abs(len(improved) - len(regressed)) >= min_flips

    note = ""
    if not shared:
        note = "no case ids in common; are these the same dataset?"
    elif improved and regressed and not significant:
        note = (f"{len(improved)} fixed, {len(regressed)} broken — churn, not "
                f"improvement. The headline rate is hiding it.")
    elif not significant and delta:
        note = "difference is within the noise for this sample size"

    return Comparison2(
        baseline_rate=baseline.pass_rate,
        candidate_rate=candidate.pass_rate,
        delta=delta,
        improved=improved,
        regressed=regressed,
        significant=significant,
        note=note,
    )
