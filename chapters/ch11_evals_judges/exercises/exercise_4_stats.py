"""EXERCISE 4 — Not fooling yourself.

    pytest chapters/ch11_evals_judges/tests -q -k stats
"""

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

    Spec:
      * total <= 0 -> (0.0, 0.0)
      * rng defaults to random.Random(0)  <- SEEDED, so tests are deterministic
      * observations = [1]*successes + [0]*(total - successes)
      * `iterations` times: draw `total` samples WITH REPLACEMENT
        (`observations[rng.randrange(total)]`) and record the mean
      * sort the means; tail = (1 - confidence) / 2
      * return (means[int(tail*iterations)], means[int((1-tail)*iterations) - 1])

    WHY YOU NEED THIS: 42/50 is 84%, and the 95% interval is roughly 72%-92%. An
    "improvement" from 84% to 88% on 50 cases is well inside the noise. People ship
    changes on differences like that constantly and revert them a month later
    having learned nothing.

    Rough guide: ~400 cases to detect a 5-point difference; ~50 is fine for 15.
    """
    # TODO: implement
    raise NotImplementedError


@dataclass
class RunComparison:
    """baseline_rate: float, candidate_rate: float, delta: float,
       improved: list[str] = [], regressed: list[str] = [],
       significant: bool = False, note: str = "" """

    baseline_rate: float
    candidate_rate: float
    delta: float


def compare_runs(
    baseline: EvalReport,
    candidate: EvalReport,
    *,
    min_flips: int = 5,
) -> RunComparison:
    """Compare two runs CASE BY CASE, not just by headline rate.

    Spec:
      * build {case id -> passed} for both; work on the ids they have IN COMMON
      * improved  = sorted ids that fail in baseline and pass in candidate
      * regressed = sorted ids that pass in baseline and fail in candidate
      * delta = candidate.pass_rate - baseline.pass_rate
      * significant = abs(len(improved) - len(regressed)) >= min_flips
      * note:
          no shared ids        -> "no case ids in common; are these the same dataset?"
          both lists non-empty
            and not significant -> "{n} fixed, {m} broken — churn, not improvement.
                                    The headline rate is hiding it."
          not significant but delta != 0 ->
                                 "difference is within the noise for this sample size"

    THE POINT: pass rates hide churn. 42/50 -> 42/50 looks like nothing changed,
    when six cases may have broken and six others got fixed. That is not stability,
    it is an UNSTABLE AGENT, and it is the most useful thing this function surfaces.

    The significance rule is a deliberately crude stand-in for McNemar's test.
    Crude and present beats rigorous and absent; `scipy.stats` has the real one.
    """
    # TODO: implement
    raise NotImplementedError
