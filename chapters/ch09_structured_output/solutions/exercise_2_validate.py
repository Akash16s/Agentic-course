"""SOLUTION — Chapter 9, Exercise 2."""

from __future__ import annotations

from typing import Any, Callable


TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
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
        if not any(TYPE_CHECKS.get(t, lambda v: True)(data) for t in types):
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
