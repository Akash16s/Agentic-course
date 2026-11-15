"""Three ways an eval lies to you, and the fix for each. Free and offline.

    python chapters/ch11_evals_judges/examples/01_fooling_yourself.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.evals.core import CaseResult, CheckResult, EvalCase, EvalReport
from agentlib.evals.judge import bootstrap_ci, compare_runs, pairwise_compare

print("=" * 76)
print("LIE 1: 'we improved from 84% to 88%'")
print("=" * 76)
for passed, total in [(42, 50), (44, 50), (420, 500), (440, 500)]:
    low, high = bootstrap_ci(passed, total)
    print(f"  {passed:>4}/{total:<5} = {passed/total:>5.0%}   95% CI "
          f"{low:>5.0%} – {high:>5.0%}   (width {high-low:>4.0%})")
print("""
  At n=50 the intervals for 84% and 88% overlap almost entirely. That
  "improvement" is indistinguishable from noise, and people ship changes on
  differences like that every day — then revert them a month later having
  learned nothing.

  At n=500 the same 4-point difference is real. Rough guide: ~400 cases to
  detect 5 points, ~50 is fine for 15.""")

print("\n" + "=" * 76)
print("LIE 2: 'nothing changed — both runs scored 42/50'")
print("=" * 76)


def report(name, outcomes):
    return EvalReport(name=name, results=[
        CaseResult(case=EvalCase(id=cid, input="q"), checks=[CheckResult("c", ok)])
        for cid, ok in outcomes.items()
    ])


rng = random.Random(7)
ids = [f"case-{i:02d}" for i in range(50)]
baseline_outcomes = {i: rng.random() < 0.84 for i in ids}
# same headline rate, six cases flipped each way
candidate_outcomes = dict(baseline_outcomes)
passing = [i for i in ids if baseline_outcomes[i]][:6]
failing = [i for i in ids if not baseline_outcomes[i]][:6]
for i in passing:
    candidate_outcomes[i] = False
for i in failing:
    candidate_outcomes[i] = True

baseline = report("baseline", baseline_outcomes)
candidate = report("candidate", candidate_outcomes)
result = compare_runs(baseline, candidate)

print(f"  baseline  : {baseline.passed}/{baseline.total} ({baseline.pass_rate:.0%})")
print(f"  candidate : {candidate.passed}/{candidate.total} ({candidate.pass_rate:.0%})")
print(f"  delta     : {result.delta:+.0%}   <- looks like nothing happened")
print()
print(f"  improved  : {len(result.improved)} cases {result.improved[:3]}...")
print(f"  regressed : {len(result.regressed)} cases {result.regressed[:3]}...")
print(f"  note      : {result.note}")
print("""
  Twelve cases changed behaviour and the headline rate moved zero. That is not
  stability, it is an UNSTABLE AGENT — and you would have shipped it believing
  the change was inert. Always read `regressed`.""")

print("\n" + "=" * 76)
print("LIE 3: 'the judge says version B is better'")
print("=" * 76)


def biased_judge(prompt):
    """A judge with no opinion at all — it always picks whatever it sees first."""
    return '{"winner": "A", "reasoning": "seems better"}'


def honest_judge(prompt):
    """A judge that actually reads: it prefers the answer that cites a source."""
    block_a = prompt.split("ANSWER A:")[1].split("ANSWER B:")[0]
    return ('{"winner": "A"}' if "[source:" in block_a else '{"winner": "B"}')


A = "The timeout is 30 seconds. [source: config.yaml]"
B = "I believe the timeout is around 30 seconds."

for label, judge in [("position-biased judge", biased_judge),
                     ("judge that actually reads", honest_judge)]:
    uncontrolled = pairwise_compare("what is the timeout?", A, B, "prefer cited claims",
                                    judge, control_position_bias=False)
    controlled = pairwise_compare("what is the timeout?", A, B, "prefer cited claims",
                                  judge, control_position_bias=True)
    print(f"  {label}")
    print(f"    without position control : winner = {uncontrolled.winner!r}")
    print(f"    with position control    : winner = {controlled.winner!r} "
          f"(orders agreed: {controlled.swapped_agreement})")
print("""
  The biased judge reports a clean win for A without position control. It has no
  opinion whatsoever — it just likes going first. Judging in both orders turns
  that into an honest "tie", and leaves the genuine preference intact.

  Two calls instead of one. A pairwise eval without this is measuring the
  judge's layout preference, not your agent.""")
