"""EXERCISE 5 — A plan-and-execute agent over real tools.

No automated test. Needs your key.

    python chapters/ch07_planning/exercises/exercise_5_planning_agent.py

TASKS
  1. Build a `PlanningAgent`:
       - a PLANNER call (cheap model, PLANNER_PROMPT) -> parse_plan
       - an EXECUTOR where `run_step` runs your Chapter 3 Agent on
         `step.description`, with `plan.render()` injected into the system prompt so
         each step can see what the others found
       - `replan=` a closure that re-plans from `plan.render()`, max_replans=1
  2. Tools: list_files, read_file, write_file (into a scratch dir only).
  3. Task: "Work out how many chapters this course has, which are longest, and write
     a summary table to scratch/summary.md."
  4. Print the plan before execution and `plan.render()` after every round.

  5. THEN COMPARE — the exercise is the comparison, not the code:
       a. Run the SAME task with a plain Chapter 3 reactive Agent. Record for each:
          total steps, total cost, wall-clock, and whether the answer was right.
       b. Run each 3 times. Is the planner more CONSISTENT, even if not cheaper?
          Consistency is usually the real win, and it is invisible in a single run.
       c. Give the planner a genuinely exploratory task ("find the bug in this
          repo"). Does the plan survive contact with step 2? This is the case where
          planning loses.
       d. Add reflection: after the final answer, have a critic check it against
          plan.render(). Does it catch anything? Now give the critic NO access to
          the plan and compare. That difference is the whole of section 3.
       e. Force a step to fail (make read_file raise on one path). Confirm the
          cascade skips dependents and the re-plan fires exactly once.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
