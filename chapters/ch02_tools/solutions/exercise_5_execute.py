"""SOLUTION — Chapter 2, Exercise 5."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentlib.llm import Message

from .exercise_3_build_tool import ToolResult
from .exercise_4_registry import ToolRegistry


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] | str = field(default_factory=dict)


def parse_tool_calls(response: Any) -> list[ToolCall]:
    raw_calls = getattr(response, "tool_calls", None)
    if not raw_calls:
        return []

    out: list[ToolCall] = []
    for call in raw_calls:
        if isinstance(call, ToolCall):
            out.append(call)
            continue
        if isinstance(call, dict):
            fn = call.get("function", {}) or {}
            out.append(
                ToolCall(
                    id=call.get("id") or "",
                    name=fn.get("name") or "",
                    arguments=fn.get("arguments") or {},
                )
            )
        else:  # an SDK object
            fn = call.function
            out.append(
                ToolCall(
                    id=getattr(call, "id", "") or "",
                    name=getattr(fn, "name", "") or "",
                    arguments=getattr(fn, "arguments", None) or {},
                )
            )
    return out


def tool_result_message(call: ToolCall, result: ToolResult) -> Message:
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "name": call.name,
        "content": result.content,
    }


def execute_tool_calls(registry: ToolRegistry, calls: list[ToolCall]) -> list[Message]:
    return [
        tool_result_message(call, registry.execute(call.name, call.arguments))
        for call in calls
    ]
