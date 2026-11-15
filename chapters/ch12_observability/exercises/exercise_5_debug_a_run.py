"""EXERCISE 5 — Find the bug with a trace.

No automated test. Needs your key.

    python chapters/ch12_observability/exercises/exercise_5_debug_a_run.py

TASKS
  1. Instrument your Chapter 3 agent end to end:
       - a root span for the run
       - TracedClient for every model call
       - TracedRegistry for every tool
       - an `event` on the root for each step (use `on_step`)
     Print `tracer.render()` and `tracer.summary()` after the run.

  2. DELIBERATELY BREAK THINGS, and find each one FROM THE TRACE ALONE. Do not
     read your own sabotage code again until you have diagnosed it:

       a. Make `read_file` return the whole file with no truncation, and point the
          agent at the largest file in this course. Find the cost spike in the
          trace. Which span? What is the ratio to the one before it?
       b. Add `time.sleep(2)` inside one tool. Find it with `slowest()`. Note how
          invisible this is if you only trace LLM calls.
       c. Make one tool raise. Find the error span AND its parent chain.
       d. Remove a tool from the registry but leave it in the system prompt. Watch
          the repeater pathology appear in the trace, and count the wasted calls.

  3. Export to JSONL. Then answer these with `jq` or plain Python over the file:
       - total cost per span NAME (which operation costs most?)
       - p50 and p95 duration for `llm.chat`
       - how many runs had at least one error span

  4. THEN THINK ABOUT PRODUCTION:
       a. Add PII redaction (Chapter 9's `RedactPII`) to anything you record.
          Confirm an email in a prompt does not reach the trace file.
       b. Implement sampling: keep 100% of traces with an error, 10% of the rest.
          Verify over 100 runs.
       c. Your trace file is now the size of your context windows. Change the
          client wrapper to record a HASH and a 200-char preview instead of the
          full prompt. Measure the file size difference.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
