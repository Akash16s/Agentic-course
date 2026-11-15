"""Structured output — getting data out of a text generator, reliably.

Promoted from Chapter 9.

Tool calling (Chapter 2) already gives you schema-constrained output for ACTIONS.
This is about the other case: when the model's ANSWER needs to be data your program
can act on, not prose a human reads.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------- extraction

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> Any | None:
    """Pull a JSON value out of a model response. None on failure, never raises.

    Handles, in order of how often they happen:
      1. clean JSON
      2. JSON inside a ```json fence, with prose either side
      3. JSON with prose either side and no fence
      4. trailing commas before } or ]
      5. a leading "json" label

    It does NOT try to fix single quotes or unquoted keys. Past a certain point you
    are writing a JavaScript parser, and the right move is to send the error back to
    the model (see `repair_loop`) rather than guess at what it meant.
    """
    if not raw or not raw.strip():
        return None

    for candidate in _candidates(raw):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _strip_trailing_commas(candidate)
            if repaired != candidate:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
    return None


def _candidates(raw: str) -> list[str]:
    """Substrings that might be the JSON, best guess first."""
    text = raw.strip()
    out = [text]

    for block in _FENCE.findall(text):
        out.append(block.strip())

    if text.lower().startswith("json"):
        out.append(text[4:].strip())

    # the widest {...} and [...] spans
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            out.append(text[start: end + 1])

    seen: set[str] = set()
    return [c for c in out if c and not (c in seen or seen.add(c))]


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


# ---------------------------------------------------------------- validation

#: JSON Schema keywords we support. A deliberate subset: these cover essentially
#: every schema you will hand a model, and implementing them yourself is the fastest
#: way to understand what the model is actually being constrained by.
SUPPORTED = {
    "type", "properties", "required", "enum", "items", "additionalProperties",
    "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems",
    "description", "title",
}

_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    # bool is a subclass of int in Python; JSON says they are different types
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(data: Any, schema: dict[str, Any], *, path: str = "$") -> list[str]:
    """Validate `data` against a JSON Schema subset. Returns human-readable errors.

    Returns a LIST rather than raising, and collects ALL errors rather than stopping
    at the first. That is the whole design: the list goes straight back to the model
    as repair instructions, and one round trip fixing four problems beats four round
    trips fixing one each.
    """
    errors: list[str] = []
    expected = schema.get("type")

    if expected:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS.get(t, lambda v: True)(data) for t in types):
            got = "null" if data is None else type(data).__name__
            errors.append(f"{path}: expected {'/'.join(types)}, got {got}")
            return errors  # no point checking constraints on the wrong type

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: {data!r} is not one of {schema['enum']}")

    if isinstance(data, dict):
        errors += _validate_object(data, schema, path)
    elif isinstance(data, list):
        errors += _validate_array(data, schema, path)
    elif isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: {data} is below minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: {data} is above maximum {schema['maximum']}")

    return errors


def _validate_object(data: dict, schema: dict, path: str) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties", {})

    for name in schema.get("required", []):
        if name not in data:
            errors.append(f"{path}: missing required field {name!r}")

    for name, value in data.items():
        if name in properties:
            errors += validate(value, properties[name], path=f"{path}.{name}")
        elif schema.get("additionalProperties") is False:
            errors.append(f"{path}: unexpected field {name!r}")

    return errors


def _validate_array(data: list, schema: dict, path: str) -> list[str]:
    errors: list[str] = []
    if "minItems" in schema and len(data) < schema["minItems"]:
        errors.append(f"{path}: needs at least {schema['minItems']} items")
    if "maxItems" in schema and len(data) > schema["maxItems"]:
        errors.append(f"{path}: allows at most {schema['maxItems']} items")
    item_schema = schema.get("items")
    if item_schema:
        for index, item in enumerate(data):
            errors += validate(item, item_schema, path=f"{path}[{index}]")
    return errors


# -------------------------------------------------------------- repair loop


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


# ---------------------------------------------------------------- guardrails


@dataclass
class GuardResult:
    """A guard's verdict. `value` may be a MODIFIED version of the input."""

    passed: bool
    value: Any
    reason: str = ""


class Guardrail:
    """Base class. A guard inspects, and may rewrite, a value."""

    name = "guardrail"

    def check(self, value: Any) -> GuardResult:  # pragma: no cover - interface
        raise NotImplementedError


class MaxLength(Guardrail):
    """Reject or truncate over-long output."""

    name = "max_length"

    def __init__(self, limit: int, *, truncate: bool = False) -> None:
        self.limit = limit
        self.truncate = truncate

    def check(self, value: Any) -> GuardResult:
        text = str(value)
        if len(text) <= self.limit:
            return GuardResult(True, value)
        if self.truncate:
            return GuardResult(True, text[: self.limit], "truncated")
        return GuardResult(False, value, f"output is {len(text)} chars, limit {self.limit}")


class Blocklist(Guardrail):
    """Reject output containing any forbidden term (case-insensitive)."""

    name = "blocklist"

    def __init__(self, terms: list[str]) -> None:
        self.terms = [t.lower() for t in terms]

    def check(self, value: Any) -> GuardResult:
        text = str(value).lower()
        hits = [t for t in self.terms if t in text]
        if hits:
            return GuardResult(False, value, f"contains blocked terms: {hits}")
        return GuardResult(True, value)


#: Deliberately conservative patterns. Real PII detection needs a proper library;
#: these catch the obvious cases and demonstrate the shape.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\+?\d[\d\s().-]{8,}\d"),
}


class RedactPII(Guardrail):
    """Replace obvious PII with placeholders. Always passes; rewrites the value."""

    name = "redact_pii"

    def __init__(self, kinds: list[str] | None = None) -> None:
        self.kinds = kinds or list(PII_PATTERNS)

    def check(self, value: Any) -> GuardResult:
        text = str(value)
        found: list[str] = []
        for kind in self.kinds:
            pattern = PII_PATTERNS.get(kind)
            if pattern is None:
                continue
            text, n = pattern.subn(f"[{kind.upper()}]", text)
            if n:
                found.append(f"{kind} x{n}")
        return GuardResult(True, text, f"redacted: {', '.join(found)}" if found else "")


@dataclass
class GuardrailReport:
    value: Any
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def run_guardrails(value: Any, guards: list[Guardrail]) -> GuardrailReport:
    """Run guards IN ORDER, each seeing the previous one's output.

    Order matters and is a design decision: put rewriting guards (redaction) before
    rejecting guards (blocklist), or you reject text that redaction would have made
    acceptable.

    Runs every guard even after one fails, so the report lists all the problems
    rather than only the first.
    """
    report = GuardrailReport(value=value)
    for guard in guards:
        result = guard.check(report.value)
        report.value = result.value
        if result.reason:
            report.notes.append(f"{guard.name}: {result.reason}")
        if not result.passed:
            report.passed = False
            report.failures.append(f"{guard.name}: {result.reason}")
    return report
