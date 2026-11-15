"""SOLUTION — Chapter 11, Exercise 4."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from agentlib.evals.core import EvalReport


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
class RunComparison:
    """The result of comparing two eval runs on the same dataset."""

    baseline_rate: float
    candidate_rate: float
    delta: float
    improved: list[str] = field(default_factory=list)   # case ids
    regressed: list[str] = field(default_factory=list)
    significant: bool = False
    note: str = ""


def compare_runs(baseline: EvalReport, candidate: EvalReport,
                 *, min_flips: int = 5) -> RunComparison:
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

    return RunComparison(
        baseline_rate=baseline.pass_rate,
        candidate_rate=candidate.pass_rate,
        delta=delta,
        improved=improved,
        regressed=regressed,
        significant=significant,
        note=note,
    )
