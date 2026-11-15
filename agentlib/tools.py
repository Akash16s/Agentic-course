"""Tools — turning Python functions into things a model can ask for.

Promoted from Chapter 2.

The whole trick: a "tool" is a JSON Schema description of a function, plus the function.
You send the schema; the model sends back a request to call it; YOU run it.
"""

from __future__ import annotations

import inspect
import json
import re
import types
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Union, get_args, get_origin

from agentlib.errors import StopSignal
from agentlib.llm import Message

# --------------------------------------------------------------------- results


@dataclass
class ToolResult:
    """What a tool run produced. Errors are DATA, not exceptions.

    The model can recover from "file not found" if you tell it. It cannot recover from
    a Python traceback that killed your process.
    """

    content: str
    is_error: bool = False

    def __str__(self) -> str:  # pragma: no cover
        return f"{'ERROR: ' if self.is_error else ''}{self.content}"


# ---------------------------------------------------------------- type mapping

_SIMPLE_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    type(None): "null",
}


def python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation into a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}  # no constraint: the model may send anything

    if annotation in _SIMPLE_TYPES:
        return {"type": _SIMPLE_TYPES[annotation]}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Literal:
        # Literal["a", "b"] -> an enum. The single most useful thing you can give a
        # model: it stops inventing values.
        return {"type": "string", "enum": list(args)}

    if origin in (list, set, tuple):
        item = python_type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item}

    if origin is dict:
        return {"type": "object"}

    if origin is Union or origin is types.UnionType:  # Optional[X] and X | None
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return python_type_to_json_schema(non_none[0])  # Optional[X] -> X
        return {"anyOf": [python_type_to_json_schema(a) for a in non_none]}

    return {"type": "string"}  # unknown: let the model send a string


def is_optional(annotation: Any) -> bool:
    """True for `X | None` / `Optional[X]`."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return type(None) in get_args(annotation)
    return False


# ------------------------------------------------------------ docstring parsing

_ARGS_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters)\s*:\s*$", re.IGNORECASE)
_ARG_LINE = re.compile(r"^\s*(\*{0,2}\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$")


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into (summary, {param_name: description}).

    The summary is everything before the Args: block. Param descriptions matter more
    than you'd think — they are the only hint the model gets about what to put in a
    field, and a vague one produces vague arguments.
    """
    if not doc:
        return "", {}

    lines = doc.strip().splitlines()
    summary_lines: list[str] = []
    params: dict[str, str] = {}
    in_args = False
    current: str | None = None

    for line in lines:
        if _ARGS_HEADER.match(line):
            in_args = True
            continue
        if in_args:
            if re.match(r"^\s*(Returns|Raises|Yields|Examples?)\s*:\s*$", line, re.I):
                break
            match = _ARG_LINE.match(line)
            if match:
                current = match.group(1).lstrip("*")
                params[current] = match.group(2).strip()
            elif current and line.strip():
                params[current] += " " + line.strip()
        else:
            summary_lines.append(line)

    return "\n".join(summary_lines).strip(), params


# ------------------------------------------------------------------ the Tool

@dataclass
class Tool:
    """A callable plus the schema that describes it to a model."""

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def spec(self) -> dict[str, Any]:
        """The OpenAI/OpenRouter `tools` array entry."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def call(self, arguments: dict[str, Any]) -> ToolResult:
        """Run the function. Never raises — failures come back as ToolResult errors."""
        try:
            value = self.func(**arguments)
        except StopSignal:
            raise  # control flow, not a failure - the agent loop catches this
        except TypeError as exc:
            return ToolResult(f"invalid arguments for {self.name}: {exc}", is_error=True)
        except Exception as exc:  # noqa: BLE001 - tool bugs must not kill the agent
            return ToolResult(f"{type(exc).__name__}: {exc}", is_error=True)
        return ToolResult(_stringify(value))


def _stringify(value: Any) -> str:
    """Tool output must be a string — it is going into a message."""
    if isinstance(value, str):
        return value
    if isinstance(value, ToolResult):
        return value.content
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):  # pragma: no cover
        return str(value)


def build_tool(func: Callable[..., Any], *, name: str | None = None,
               description: str | None = None) -> Tool:
    """Derive a Tool from a plain Python function's signature + docstring."""
    signature = inspect.signature(func)
    hints = typing.get_type_hints(func)
    summary, param_docs = parse_docstring(func.__doc__)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in signature.parameters.items():
        if pname in ("self", "cls") or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = hints.get(pname, param.annotation)
        schema = python_type_to_json_schema(annotation)
        if pname in param_docs:
            schema["description"] = param_docs[pname]
        properties[pname] = schema
        # required == "no default AND not Optional"
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
    """Decorator. `@tool` or `@tool(name="...")`.

    >>> @tool
    ... def add(a: int, b: int) -> int:
    ...     '''Add two numbers.'''
    ...     return a + b
    >>> add.name
    'add'
    """

    def wrap(f: Callable[..., Any]) -> Tool:
        return build_tool(f, name=name, description=description)

    return wrap(func) if func is not None else wrap


# --------------------------------------------------------------- the registry


class ToolRegistry:
    """The set of tools an agent may use, and the dispatcher that runs them."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.register(t)

    def register(self, t: Tool | Callable[..., Any]) -> Tool:
        if not isinstance(t, Tool):
            t = build_tool(t)
        if t.name in self._tools:
            raise ValueError(f"tool {t.name!r} is already registered")
        self._tools[t.name] = t
        return t

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[dict[str, Any]]:
        """The `tools=[...]` argument for the API call."""
        return [t.spec() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any] | str) -> ToolResult:
        """Run one tool by name. Bad name, bad JSON and tool crashes all come back as
        error ToolResults, because all three are things the model can retry."""
        t = self._tools.get(name)
        if t is None:
            return ToolResult(
                f"unknown tool {name!r}. Available: {', '.join(self.names) or 'none'}",
                is_error=True,
            )
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as exc:
                return ToolResult(f"arguments were not valid JSON: {exc}", is_error=True)
        if not isinstance(arguments, dict):
            return ToolResult("arguments must be a JSON object", is_error=True)
        return t.call(arguments)


# ------------------------------------------------------- tool-call plumbing


@dataclass
class ToolCall:
    """One request from the model to run one tool."""

    id: str
    name: str
    arguments: dict[str, Any] | str = field(default_factory=dict)


def parse_tool_calls(response: Any) -> list[ToolCall]:
    """Pull ToolCalls out of an LLMResponse or a raw provider message."""
    raw_calls = getattr(response, "tool_calls", None)
    if raw_calls is None:
        return []
    out: list[ToolCall] = []
    for call in raw_calls:
        if isinstance(call, ToolCall):
            out.append(call)
            continue
        fn = call.get("function", {}) if isinstance(call, dict) else call.function
        out.append(
            ToolCall(
                id=(call.get("id") if isinstance(call, dict) else call.id) or "",
                name=fn.get("name") if isinstance(fn, dict) else fn.name,
                arguments=(fn.get("arguments") if isinstance(fn, dict) else fn.arguments)
                or {},
            )
        )
    return out


def tool_result_message(call: ToolCall, result: ToolResult) -> Message:
    """The `role: tool` message that carries a result back to the model.

    `tool_call_id` is not optional — it is how the model pairs a result with its
    request when it made several at once.
    """
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "name": call.name,
        "content": result.content,
    }


def execute_tool_calls(registry: ToolRegistry, calls: list[ToolCall]) -> list[Message]:
    """Run every requested call and return one tool message per call, in order.

    One message per call, always — a model that asked for three tools and got two
    results back will hallucinate the third or error out.
    """
    return [
        tool_result_message(call, registry.execute(call.name, call.arguments))
        for call in calls
    ]
