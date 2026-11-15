"""SOLUTION — Chapter 2, Exercise 3."""

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
    content: str
    is_error: bool = False


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def call(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            value = self.func(**arguments)
        except TypeError as exc:
            return ToolResult(f"invalid arguments for {self.name}: {exc}", is_error=True)
        except Exception as exc:  # noqa: BLE001 - a tool bug must not kill the agent
            return ToolResult(f"{type(exc).__name__}: {exc}", is_error=True)
        return ToolResult(stringify(value))


def stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, ToolResult):
        return value.content
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def build_tool(
    func: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
) -> Tool:
    signature = inspect.signature(func)
    try:
        hints = typing.get_type_hints(func)
    except Exception:  # noqa: BLE001 - unresolvable forward refs shouldn't be fatal
        hints = {}
    summary, param_docs = parse_docstring(func.__doc__)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in signature.parameters.items():
        if pname in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        annotation = hints.get(pname, param.annotation)
        schema = python_type_to_json_schema(annotation)
        if pname in param_docs:
            schema["description"] = param_docs[pname]
        properties[pname] = schema

        if param.default is inspect.Parameter.empty and not is_optional(annotation):
            required.append(pname)

    return Tool(
        name=name or func.__name__,
        description=description or summary or func.__name__,
        parameters={"type": "object", "properties": properties, "required": required},
        func=func,
    )


def tool(func: Callable[..., Any] | None = None, *, name: str | None = None,
         description: str | None = None):
    def wrap(f: Callable[..., Any]) -> Tool:
        return build_tool(f, name=name, description=description)

    # bare @tool -> func is the function;  @tool(...) -> func is None
    return wrap(func) if func is not None else wrap
