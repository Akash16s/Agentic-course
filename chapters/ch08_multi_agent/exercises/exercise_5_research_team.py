"""EXERCISE 5 — A research team, measured against one agent.

No automated test. Needs your key. The MEASUREMENT is the exercise.

    python chapters/ch08_multi_agent/exercises/exercise_5_research_team.py

TASKS
  1. Build an orchestrator-worker research team over this course directory:
       - a PLANNER call that splits a question into 3-5 independent subtasks
       - workers: each is a Chapter 3 Agent with read_file/list_files
       - fan_out with max_parallel=3
       - a SYNTHESISER call using synthesis_prompt
     Question: "Which chapters cover memory, what does each one add, and which
     has the most exercises?"

  2. Build the SAME thing as ONE Chapter 3 agent with the same tools.

  3. MEASURE BOTH, three runs each:
       - wall-clock seconds
       - total tokens and total cost
       - was the answer correct? (you know the right answer; score it yourself)
       - how much did the three runs differ from each other?

  4. WRITE DOWN THE NUMBERS before you interpret them. Then answer:
       a. Did multi-agent win on wall-clock? By how much? Was the fan-out actually
          parallel, or did one slow worker dominate?
       b. Did it cost more? The chapter predicts roughly 2x. Was it?
       c. Was it more CONSISTENT across the three runs? Consistency is often the
          real win and it is invisible in a single run.
       d. Kill one worker (make it raise). Does the synthesiser notice? Now delete
          the "[FAILED: ...]" line from synthesis_prompt and try again. Read the
          answer it produces about the missing topic. That is section 3's warning,
          reproduced.
       e. Given your numbers: would you ship the multi-agent version? Write one
          honest paragraph. "No" is a perfectly good result for this exercise, and
          the most likely one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
