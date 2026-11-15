"""EXERCISE 5 — The same agent, three ways, measured.

No automated test. Needs your key, and `pip install langgraph` for part 3.

    python chapters/ch17_frameworks/exercises/exercise_5_compare.py

THE TASK (same for all three)
  A document agent over this course directory with list_files, read_file and
  submit_answer. Question: "Which chapters mention circuit breakers, and what
  does each say about them?"

BUILD IT THREE TIMES
  A. Your Chapter 3 `Agent`
  B. Your `StateGraph` from this chapter
  C. LangGraph's `create_react_agent`

MEASURE, five runs each
  - lines of code you wrote
  - total tokens and cost per run
  - wall-clock
  - correctness (score it yourself against a known answer)
  - MOST IMPORTANTLY: how long it takes you to answer the questions below

THE QUESTIONS — this is the actual exercise
  1. For each of the three, print the EXACT messages sent on the final model call.
     For A and B you know how. For C you will have to find the hook, or set a
     debug env var, or read the source. Time yourself.
     If you cannot do this for C, you have learned something important about
     shipping C to production.
  2. Introduce a bug: make `read_file` return the wrong file's contents. Find it
     from a stack trace in each version. Compare the traces.
  3. Add a cost limit of $0.02 to each. How many lines? Where does it go?
  4. Add Chapter 12 tracing to each. Which was easiest? Which fought you?
  5. Make the agent resumable — kill it mid-run and continue. A and B need
     Chapter 15's machinery; C has a checkpointer. Now the trade flips. By how
     much?

THEN WRITE IT DOWN
  One page: which would you ship, for what kind of project, and why. Name the
  specific capability that decides it, not a vibe. "LangGraph, because I need
  interrupt-and-resume for human approval and I am not building a checkpointer"
  is an answer. "LangGraph, because it is more standard" is not.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
