"""SOLUTION — Chapter 2, Exercise 1."""

from __future__ import annotations

import types
from typing import Any, Literal, Union, get_args, get_origin

SIMPLE_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    type(None): "null",
}


def python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    import inspect

    if annotation is inspect.Parameter.empty or annotation is Any or annotation is None:
        return {}

    if annotation in SIMPLE_TYPES:
        return {"type": SIMPLE_TYPES[annotation]}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Literal:
        return {"type": "string", "enum": list(args)}

    if origin in (list, set, tuple) or annotation in (list, set, tuple):
        item = python_type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item}

    if origin is dict or annotation is dict:
        return {"type": "object"}

    # BOTH union spellings: typing.Union[...] and the 3.10+ `X | None`
    if origin is Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return python_type_to_json_schema(non_none[0])
        return {"anyOf": [python_type_to_json_schema(a) for a in non_none]}

    return {"type": "string"}


def is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return type(None) in get_args(annotation)
    return False
