"""The four ways a plan deadlocks, and the parse-time repairs. Free and offline.

    python chapters/ch07_planning/examples/01_deadlocks.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.planning import Plan, PlanExecutor, PlanStep, StepStatus, parse_plan

BAD_PLANS = {
    "dangling dependency (step 9 does not exist)":
        '[{"id":1,"description":"read config","depends_on":[9]}]',
    "cycle (1 -> 2 -> 1)":
        '[{"id":1,"description":"a","depends_on":[2]},'
        ' {"id":2,"description":"b","depends_on":[1]}]',
    "self-dependency":
        '[{"id":1,"description":"a","depends_on":[1]}]',
    "three-way cycle":
        '[{"id":1,"description":"a","depends_on":[3]},'
        ' {"id":2,"description":"b","depends_on":[1]},'
        ' {"id":3,"description":"c","depends_on":[2]}]',
}

print("=" * 74)
print("WITHOUT REPAIR: every one of these hangs")
print("=" * 74)
print(f"{'malformed plan':<46} ready steps")
print("-" * 74)
import json as _json
for label, raw in BAD_PLANS.items():
    # build the plan verbatim, skipping parse_plan's repairs
    raw_steps = [
        PlanStep(id=int(d["id"]), description=d["description"],
                 depends_on=[int(x) for x in d.get("depends_on", [])])
        for d in _json.loads(raw)
    ]
    unrepaired = Plan(goal="g", steps=raw_steps)
    ready = [s.id for s in unrepaired.ready_steps()]
    print(f"{label:<46} {ready or 'NONE -> hang'}")

print("\n" + "=" * 74)
print("WITH parse_plan's REPAIRS: always something to run")
print("=" * 74)
print(f"{'malformed plan':<46} ready steps")
print("-" * 74)
for label, raw in BAD_PLANS.items():
    repaired = parse_plan("g", raw)
    print(f"{label:<46} {[s.id for s in repaired.ready_steps()]}")

print("\n" + "=" * 74)
print("THE FOURTH DEADLOCK: a failed step blocking its dependents")
print("=" * 74)

plan = parse_plan("g", '[{"id":1,"description":"fetch data"},'
                       ' {"id":2,"description":"analyse","depends_on":[1]},'
                       ' {"id":3,"description":"report","depends_on":[2]}]')


def fail_first(step, p):
    if step.id == 1:
        raise ConnectionError("the API is down")
    return "ok"


run = PlanExecutor(fail_first, max_rounds=10).execute(plan)
print(plan.render())
print(f"\nrounds used: {run.rounds} of 10   (skip_blocked ended it immediately)")
print(f"succeeded  : {run.succeeded}")
print("""
Without skip_blocked, steps 2 and 3 stay PENDING forever. `ready_steps()` returns
nothing, the plan is never `complete`, and the executor burns all 10 rounds doing
absolutely nothing before giving up with a useless error.

Note what all four failures have in common: NOTHING RAISES. They present as a hang.
That is why the repairs live at parse time — by the time you are debugging a hang,
you have already lost the afternoon.""")
