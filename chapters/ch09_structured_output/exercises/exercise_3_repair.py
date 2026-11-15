"""EXERCISE 3 — The repair loop.

    pytest chapters/ch09_structured_output/tests -q -k repair
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .exercise_1_extract import extract_json
from .exercise_2_validate import validate

REPAIR_PROMPT = """\
Your previous response could not be used.

{problem}

Required schema:
{schema}

Return ONLY the corrected JSON. No explanation, no markdown fence."""


@dataclass
class ExtractResult:
    """value: Any = None, errors: list[str] = [], attempts: int = 0, raw: str = "" """

    value: Any = None

    @property
    def ok(self) -> bool:
        """No errors AND value is not None."""
        # TODO: implement
        raise NotImplementedError


def repair_prompt(errors: list[str], schema: dict[str, Any], raw: str) -> str:
    """Build the follow-up that tells the model exactly what was wrong.

    Spec:
      * no errors (i.e. it wasn't parseable at all) ->
            problem = f"It was not valid JSON. You sent:\\n{raw[:500]}"
      * otherwise ->
            problem = "Validation errors:\\n" + one "- {error}" line each
      * return REPAIR_PROMPT.format(problem=..., schema=json.dumps(schema, indent=2))

    Truncate `raw` — a model that produced 8,000 characters of the wrong thing does
    not need all 8,000 read back to it, and you would pay for the tokens twice.

    SPECIFICITY IS THE WHOLE POINT. "That was invalid, try again" gets you something
    similar back. "$.items[2].price: expected number, got str" gets it fixed on the
    next attempt essentially every time.
    """
    # TODO: implement
    raise NotImplementedError


def extract_validated(
    call_model: Callable[[str | None], str],
    schema: dict[str, Any],
    *,
    max_attempts: int = 3,
) -> ExtractResult:
    """Call, parse, validate; on failure feed the errors back. NEVER raises.

    `call_model(feedback)` gets None on the first attempt, then a repair prompt.

    Spec:
      result = ExtractResult()
      feedback = None
      for attempt in 1..max_attempts:
          result.attempts = attempt
          raw = call_model(feedback);  result.raw = raw
          value = extract_json(raw)
          if value is None:
              result.value = None
              result.errors = ["response was not parseable as JSON"]
              feedback = repair_prompt([], schema, raw)
              continue
          errors = validate(value, schema)
          result.value, result.errors = value, errors
          if not errors: return result      # success, stop early
          feedback = repair_prompt(errors, schema, raw)
      return result                          # exhausted; errors explain why

    CAP AT 2-3. Two attempts fixes the overwhelming majority. If three fail, the
    SCHEMA is the problem — models are markedly worse at deeply nested objects, and
    flattening fixes more cases than another retry ever will.
    """
    # TODO: implement
    raise NotImplementedError
