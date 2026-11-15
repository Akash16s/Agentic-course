"""EXERCISE 5 — A real agent on a real task.

No automated test. Run it, watch the trace, then deliberately break it.

    python chapters/ch03_react_loop/exercises/exercise_5_real_agent.py

TASKS
  1. Build a small "filesystem researcher" agent with three tools:
        list_files(directory: str = ".") -> list[str]
        read_file(path: str, max_chars: int = 4000) -> str
        submit_answer(answer: str) -> str     # raises StopSignal(answer)
     Point it at this course directory and ask:
        "How many chapters does this course have, and what is chapter 6 about?"
  2. Pass `on_step=` a callback that prints, per step:
        step index | tools called | tokens | cumulative cost
  3. Print the full trace at the end: `result.tool_sequence`, `stop_reason`, `cost`.

  4. NOW BREAK IT — this is the exercise:
       a. Set `max_steps=2`. Confirm you get MAX_STEPS and a partial answer, not a crash.
       b. Set `budget_usd=0.0005`. Confirm BUDGET, and that `result.cost` still reports
          the money you actually spent.
       c. Remove `submit_answer`. Does it still terminate? How many extra steps?
       d. Make `read_file` raise on every call. Does the agent route around it or die?
       e. Give `list_files` a deliberately useless return (always `[]`). Watch for the
          repeater pathology, then check `detect_repetition` catches it.
       f. Ask a question needing two files at once. Do you see parallel tool_calls,
          and does the timing show them overlapping?
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.errors import StopSignal
from agentlib.llm import LLMClient
from agentlib.tools import ToolRegistry, tool

# TODO: import your Agent from exercise_4_agent (or agentlib.agent for the reference)

COURSE_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    # TODO 1: define the three tools. Keep read_file bounded — an unbounded tool
    #         result is the fastest way to blow your context window.
    # TODO 2: agent = Agent(LLMClient(), tools=..., system=..., max_steps=12,
    #                       budget_usd=0.10, on_step=...)
    # TODO 3: result = agent.run("...")
    # TODO 4: print the trace
    raise NotImplementedError


if __name__ == "__main__":
    main()
