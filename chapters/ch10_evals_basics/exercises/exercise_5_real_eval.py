"""EXERCISE 5 — Actually evaluate your agent.

No automated test. Needs your key. This is the most valuable exercise in the course.

    python chapters/ch10_evals_basics/exercises/exercise_5_real_eval.py

TASKS
  1. BUILD THE DATASET FIRST, before you look at any code. 30 cases, in a JSONL
     file, for a "codebase question answering" agent pointed at this course:
       - 20 normal questions with known answers
         ("How many exercises does chapter 6 have?", "Which chapter covers MCP?")
       -  5 negative cases: questions it should refuse or say it cannot answer
         ("What is my bank balance?", "Delete chapter 3")
       -  5 nasty ones: empty input, a 2,000-word question, a question in another
         language, an ambiguous one, one whose premise is false
         ("Why does chapter 25 contradict chapter 4?")

  2. Build the agent (Chapter 3) with list_files and read_file.

  3. Write the checks. At minimum:
       expected_contains()          for the normal cases
       tool_called("read_file")     it must actually look, not guess
       max_steps(8)
       max_cost(0.05)
       succeeded()
       tool_not_called("write_file")   on every case (there is no write_file —
                                        add one that raises, and prove it is never
                                        reached)

  4. Run it. Read `report.summary()` and `report.failure_detail()`.

  5. NOW THE ACTUAL EXERCISE — improve it deliberately:
       a. Record your baseline pass rate. Write it down.
       b. Look at `failures_by_check()`. Fix the single most common failure — and
          predict, before you re-run, what the new number will be.
       c. Re-run. Were you right? Being wrong here is the most useful thing that
          can happen: it means your model of the agent was wrong, and now you know.
       d. Repeat three times. Keep a log: change, predicted, actual.
       e. Now make the agent WORSE on purpose (delete the system prompt). Does the
          suite catch it? If the score barely moves, YOUR CASES ARE TOO EASY —
          that is the real finding, and it is the most common problem with a first
          eval suite.
       f. Swap to the cheapest model you can find. What is the accuracy/cost
          trade? Would you take it?
       g. Set a gate at your baseline and wire it into a script that exits non-zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
