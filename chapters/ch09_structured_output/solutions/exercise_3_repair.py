"""SOLUTION — Chapter 9, Exercise 3."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .exercise_1_extract import extract_json
from .exercise_2_validate import validate


@dataclass
class ExtractResult:
    value: Any = None
    errors: list[str] = field(default_factory=list)
    attempts: int = 0
    raw: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors and self.value is not None


REPAIR_PROMPT = """\
Your previous response could not be used.

{problem}

Required schema:
{schema}

Return ONLY the corrected JSON. No explanation, no markdown fence."""


def repair_prompt(errors: list[str], schema: dict[str, Any], raw: str) -> str:
    """Build the follow-up message that tells the model exactly what was wrong.

    Specific errors, not "that was invalid". A model told
    `$.items[2].price: expected number, got str` fixes it on the next attempt
    essentially always; a model told "invalid JSON" re-emits something similar.
    """
    if not errors:
        problem = f"It was not valid JSON. You sent:\n{raw[:500]}"
    else:
        problem = "Validation errors:\n" + "\n".join(f"- {e}" for e in errors)
    return REPAIR_PROMPT.format(problem=problem, schema=json.dumps(schema, indent=2))


def extract_validated(
    call_model: Callable[[str | None], str],
    schema: dict[str, Any],
    *,
    max_attempts: int = 3,
) -> ExtractResult:
    """Call, parse, validate, and on failure send the errors back. Never raises.

    `call_model(feedback)` is called with None first, then with a repair prompt.

    Two attempts fixes the overwhelming majority of failures. Three is a reasonable
    cap. If it fails three times the schema is probably the problem — models
    struggle with deep nesting, and flattening it fixes more cases than more retries.
    """
    result = ExtractResult()
    feedback: str | None = None

    for attempt in range(1, max_attempts + 1):
        result.attempts = attempt
        raw = call_model(feedback)
        result.raw = raw

        value = extract_json(raw)
        if value is None:
            result.value = None
            result.errors = ["response was not parseable as JSON"]
            feedback = repair_prompt([], schema, raw)
            continue

        errors = validate(value, schema)
        result.value = value
        result.errors = errors
        if not errors:
            return result
        feedback = repair_prompt(errors, schema, raw)

    return result
