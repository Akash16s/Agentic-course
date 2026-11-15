"""EXERCISE 5 — The same extraction task, four ways.

No automated test. Needs your key. The COMPARISON is the exercise.

    python chapters/ch09_structured_output/exercises/exercise_5_extractor.py

THE TASK
  Given a customer support message, extract:
      {"sentiment": "positive|negative|neutral",
       "urgency": 1-5,
       "topics": [str],
       "needs_human": bool,
       "summary": str (max 200 chars)}

  Write 15 test messages by hand, including three awkward ones (empty, a wall of
  text, one in another language).

BUILD ALL FOUR
  A. prompt + extract_json, no validation      (the naive baseline)
  B. prompt + extract_json + validate + repair (extract_validated)
  C. tool calling: one `submit_analysis` tool with the schema as its parameters,
     forced with tool_choice
  D. native structured output: pass `response_format={"type":"json_schema", ...}`
     through OpenRouter. EXPECT THIS TO FAIL OR BE IGNORED on some models — note
     exactly which, and what the failure looks like. That is useful knowledge.

MEASURE, over your 15 messages x 3 runs
  - % that produced a valid, schema-conforming object first try
  - % after repair
  - average extra calls
  - total cost
  - which FIELD fails most often

THEN INVESTIGATE
  a. Remove every `description` from the schema. Re-measure. The difference is
     what field descriptions are worth.
  b. Change `sentiment` from an enum to a plain string. Count how many novel
     values the model invents.
  c. Nest the schema three levels deep (topics become objects with sub-objects).
     Does the repair loop still converge in 3 attempts?
  d. Make the repair prompt vague ("that was invalid, try again"). Compare the
     repair success rate against the specific version. This is the single biggest
     lever in the chapter — measure it.
  e. Run A against your cheapest model and your best one. How much of reliability
     is technique and how much is just model quality?
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
