"""EXERCISE 3 — Function -> Tool.

WHY: This is `@tool` in every framework you will ever use. Once you have written it, you
will know exactly what LangChain's `StructuredTool.from_function` is doing, and why it
sometimes produces a schema you did not expect.

    pytest chapters/ch02_tools/tests -q -k build_tool
"""

from __future__ import annotations

import inspect
import json
import typing
from dataclasses import dataclass
from typing import Any, Callable

from .exercise_1_schema import is_optional, python_type_to_json_schema
from .exercise_2_docstring import parse_docstring


@dataclass
class ToolResult:
    """What a tool run produced. Errors are DATA, not exceptions."""

    content: str
    is_error: bool = False


@dataclass
class Tool:
    """A callable plus the schema that describes it to a model."""

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def spec(self) -> dict[str, Any]:
        """The entry that goes in the API's `tools` array.

        Exact shape:
            {"type": "function",
             "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        # TODO: implement
        raise NotImplementedError

    def call(self, arguments: dict[str, Any]) -> ToolResult:
        """Run `self.func(**arguments)`.

        MUST NOT RAISE. Spec:
          * success           -> ToolResult(stringify(value), is_error=False)
          * TypeError         -> ToolResult(f"invalid arguments for {name}: {exc}",
                                            is_error=True)
          * any other Exception -> ToolResult(f"{type(exc).__name__}: {exc}",
                                              is_error=True)

        Catching TypeError separately is worth it: "invalid arguments" tells the model
        to fix its call, while a bare traceback tells it nothing.
        """
        # TODO: implement
        raise NotImplementedError


def stringify(value: Any) -> str:
    """Turn a tool's return value into message content.

    Spec:
      * str          -> unchanged
      * ToolResult   -> its .content
      * anything else-> json.dumps(value, default=str)
      * if json.dumps raises TypeError/ValueError -> str(value)

    Why not just `str(value)`? Because `str({"a": 1})` gives `"{'a': 1}"` — single
    quotes, not JSON. Models parse that badly and then produce it badly.
    """
    # TODO: implement
    raise NotImplementedError


def build_tool(
    func: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
) -> Tool:
    """Derive a Tool from a function.

    Spec:
      * name        = `name` arg, else func.__name__
      * description = `description` arg, else the docstring summary, else func.__name__
      * parameters  = {"type": "object", "properties": {...}, "required": [...]}

    For each parameter in `inspect.signature(func).parameters`:
      * SKIP `self`, `cls`, `*args` (VAR_POSITIONAL) and `**kwargs` (VAR_KEYWORD)
      * get its annotation from `typing.get_type_hints(func)`, falling back to
        `param.annotation` (get_type_hints resolves string annotations, which you get
        whenever the module has `from __future__ import annotations` — as this one does)
      * schema = python_type_to_json_schema(annotation)
      * if the docstring documented it, add schema["description"]
      * add to `required` iff it has NO default AND is not Optional

    >>> def add(a: int, b: int = 0) -> int:
    ...     '''Add numbers.'''
    ...     return a + b
    >>> build_tool(add).parameters["required"]
    ['a']
    """
    # TODO: implement
    raise NotImplementedError


def tool(func: Callable[..., Any] | None = None, *, name: str | None = None,
         description: str | None = None):
    """Decorator form. Must support BOTH:

        @tool
        def f(...): ...

        @tool(name="custom")
        def g(...): ...

    The trick: when used bare, `func` is the function. When used with arguments, `func`
    is None and you must return a decorator. Both return a `Tool`, not a function —
    which means the name is rebound to a Tool object. That is intentional and is what
    the registry expects.
    """
    # TODO: implement
    raise NotImplementedError
