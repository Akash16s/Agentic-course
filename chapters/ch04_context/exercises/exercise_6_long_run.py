"""EXERCISE 6 — An agent that survives a long session.

No automated test. Needs your key.

    python chapters/ch04_context/exercises/exercise_6_long_run.py

TASKS
  1. Build a `ManagedAgent` that wraps your Chapter 3 Agent and, before every model
     call, does this in order:
        a. truncate_tool_results(messages, max_chars=3000)
        b. if estimated tokens > 70% of budget.available_for_history:
               compact(messages, summarise=..., keep_recent=6)
        c. if STILL over: trim_messages(..., keep_first=2, keep_last=6)
     The order matters. Truncation is free, compaction costs a call, trimming
     loses information permanently — so do the cheap lossless thing first.
  2. Use a CHEAP model for the summariser and your normal model for the agent.
     Print which model each call used and what each cost.
  3. Give it a task that needs many file reads (e.g. "summarise what every chapter
     of this course covers") and a small `context_window` — try 8000 — so that
     compaction actually fires several times.

  4. THEN INVESTIGATE:
       a. Print the message list before and after each compaction. Is the summary
          specific (paths, numbers, names) or vague? Improve COMPACTION_PROMPT until
          it is specific.
       b. After a compaction, ask the agent about something only mentioned in the
          summarised part. Does it still know?
       c. Remove `keep_first=2`. Does the agent eventually forget its own task?
       d. Break `message_pairs` on purpose (return `[[m] for m in messages]`) and
          watch the provider reject the request. Read the exact error text — you want
          to recognise it instantly when you meet it for real.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.llm import LLMClient

# TODO: import your ContextBudget / compact / trim_messages / truncate_tool_results


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
