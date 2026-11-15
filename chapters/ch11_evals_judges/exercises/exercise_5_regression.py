"""EXERCISE 5 — A regression suite you would actually gate CI on.

No automated test. Needs your key.

    python chapters/ch11_evals_judges/exercises/exercise_5_regression.py

TASKS
  1. Extend your Chapter 10 dataset with 10 cases that CANNOT be checked by
     assertion — "summarise chapter 4 in three sentences", "explain the difference
     between short and long term memory to a beginner".

  2. Write a real rubric for them. Anchor every point on the scale to something
     observable. Iterate on it: grade five responses yourself first, then have the
     judge grade the same five and compare. Keep editing the rubric until you and
     the judge agree on at least four of five. THIS CALIBRATION STEP IS THE
     EXERCISE — a rubric you have not calibrated is a random number generator with
     good manners.

  3. Add trajectory checks with `trajectory_contains`.

  4. Run the suite THREE TIMES against an unchanged agent at temperature 0.
     Record the three pass rates. That spread is your noise floor. Write it down —
     any future "improvement" smaller than this number is not one.

  5. Now make a real change (a better system prompt). Run three more times.
     Use `compare_runs` and `bootstrap_ci`. Is the difference bigger than the noise
     floor you measured in step 4?

  6. THEN INVESTIGATE:
       a. Grade with the SAME model that generated the answers, then a different
          one. Does the same-model judge score higher? By how much?
       b. Run `pairwise_compare` with `control_position_bias=False` across 20
          comparisons, then with it on. How many results changed? That is how much
          position bias was costing you.
       c. Replace your careful rubric with "rate this 1-5". Re-run. How much did
          the variance across three runs increase?
       d. Break the judge's JSON on purpose (make call_model return prose). Confirm
          scores go DOWN, not up. If you had written it to fail open, your suite
          would now be reporting a silent improvement.
       e. Write the CI script: smoke suite on every run, exit non-zero below your
          gate, and append the report to a JSONL history file so you can plot drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
