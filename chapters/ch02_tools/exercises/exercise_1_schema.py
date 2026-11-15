"""EXERCISE 1 — Python types to JSON Schema.

WHY: The schema is the contract. It is the only thing preventing the model from sending
`{"town": "Delhi"}` instead of `{"city": "Delhi"}`, and the only place you can express
"this must be one of these three values".

    pytest chapters/ch02_tools/tests -q -k schema
"""

from __future__ import annotations

import types
import typing
from typing import Any, Literal, Union, get_args, get_origin

#: Direct one-to-one mappings.
SIMPLE_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",     # JSON Schema splits int/number; Python's float maps to number
    bool: "boolean",
    type(None): "null",
}


def python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Convert a type annotation to a JSON Schema fragment.

    Spec, in this order (order matters — check the special cases before the general):

      1. `annotation is Any` or the annotation is missing  -> {}  (no constraint)
      2. in SIMPLE_TYPES                                   -> {"type": <name>}
      3. Literal["a", "b"]        -> {"type": "string", "enum": ["a", "b"]}
      4. list/set/tuple[X]        -> {"type": "array", "items": <schema of X>}
         bare `list`             -> {"type": "array", "items": {}}
      5. dict[...]                -> {"type": "object"}
      6. Union / `X | None`:
            exactly one non-None member -> that member's schema (Optional[X] is just X;
                                           optionality lives in `required`, not in `type`)
            several                     -> {"anyOf": [<each>]}
      7. anything else            -> {"type": "string"}  (let the model send a string)

    Use `get_origin` / `get_args` from typing. For `X | None` on Python 3.10+ the origin
    is `types.UnionType`, NOT `typing.Union` — you must check both or `int | None` will
    silently fall through to the string default. (That exact bug was in my first draft.)

    >>> python_type_to_json_schema(str)
    {'type': 'string'}
    >>> python_type_to_json_schema(Literal["a", "b"])
    {'type': 'string', 'enum': ['a', 'b']}
    """
    # TODO: implement
    raise NotImplementedError


def is_optional(annotation: Any) -> bool:
    """True if `annotation` is `Optional[X]` / `X | None`.

    Used to decide `required`. A parameter is required when it has no default AND is
    not optional.

    >>> is_optional(int | None)
    True
    >>> is_optional(int)
    False
    """
    # TODO: implement
    raise NotImplementedError
