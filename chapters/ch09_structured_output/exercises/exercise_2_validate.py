"""EXERCISE 2 — A JSON Schema validator.

WHY BUILD ONE: `jsonschema` exists and is good. But writing the subset yourself is
the fastest way to understand precisely what a schema does and does not constrain —
which matters, because "the model returned the wrong shape" is usually "the schema
never said it couldn't".

    pytest chapters/ch09_structured_output/tests -q -k validate
"""

from __future__ import annotations

from typing import Any, Callable

TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    # TODO: add "integer", "number", "boolean", "null"
    #
    # THE TRAP: in Python `isinstance(True, int)` is True, because bool subclasses
    # int. JSON says they are different types. So the integer check must be
    #     isinstance(v, int) and not isinstance(v, bool)
    # Without the `and not`, {"age": true} validates against {"type": "integer"}.
    # This bug sits in validators for years.
}


def validate(data: Any, schema: dict[str, Any], *, path: str = "$") -> list[str]:
    """Validate `data` against a JSON Schema subset. Return a list of errors.

    RETURNS A LIST, NEVER RAISES, AND COLLECTS EVERY ERROR. Both of those are the
    point: the list goes straight back to the model as repair instructions, and one
    round trip fixing four problems beats four round trips fixing one each.

    `path` accumulates so errors are locatable: "$.items[2].price".

    Spec, in this order:

      1. `type` (may be a string or a list of strings):
           if nothing matches ->
               f"{path}: expected {'/'.join(types)}, got {name}"
           where `name` is "null" for None, else type(data).__name__
           THEN RETURN IMMEDIATELY — checking minLength on an integer is noise.

      2. `enum`: data not in it ->
           f"{path}: {data!r} is not one of {schema['enum']}"

      3. dict -> _validate_object ; list -> _validate_array

      4. str:  minLength -> f"{path}: shorter than minLength {n}"
               maxLength -> f"{path}: longer than maxLength {n}"

      5. int/float (NOT bool):
               minimum   -> f"{path}: {data} is below minimum {n}"
               maximum   -> f"{path}: {data} is above maximum {n}"
    """
    # TODO: implement
    raise NotImplementedError


def _validate_object(data: dict, schema: dict, path: str) -> list[str]:
    """Spec:
      * for each name in schema["required"] missing from data:
            f"{path}: missing required field {name!r}"
      * for each key in data:
            in properties          -> recurse with path f"{path}.{key}"
            not in properties AND schema.get("additionalProperties") is False ->
                f"{path}: unexpected field {key!r}"
            otherwise              -> ignore (extras are allowed by default,
                                      which is what JSON Schema says)
    """
    # TODO: implement
    raise NotImplementedError


def _validate_array(data: list, schema: dict, path: str) -> list[str]:
    """Spec:
      * minItems -> f"{path}: needs at least {n} items"
      * maxItems -> f"{path}: allows at most {n} items"
      * items    -> recurse for each element with path f"{path}[{i}]"
    """
    # TODO: implement
    raise NotImplementedError
