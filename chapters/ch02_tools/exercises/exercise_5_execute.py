"""EXERCISE 5 — Tool-call plumbing.

WHY: This is the bit between "the model asked" and "the model can see the answer". Get
the message shapes wrong and the provider returns a 400 you will stare at for an hour.

    pytest chapters/ch02_tools/tests -q -k execute
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentlib.llm import Message

from .exercise_3_build_tool import ToolResult
from .exercise_4_registry import ToolRegistry


@dataclass
class ToolCall:
    """One request from the model to run one tool."""

    id: str
    name: str
    #: Still a JSON STRING when it comes from a real provider. The registry parses it.
    arguments: dict[str, Any] | str = field(default_factory=dict)


def parse_tool_calls(response: Any) -> list[ToolCall]:
    """Pull `ToolCall`s out of an LLMResponse (or anything with `.tool_calls`).

    Spec:
      * no `tool_calls` attribute, or it is None -> []
      * each raw call may be:
          - already a ToolCall        -> pass through
          - a dict (our LLMResponse)  -> {"id", "function": {"name", "arguments"}}
          - an SDK object             -> call.id, call.function.name,
                                         call.function.arguments
      * missing id -> "" ; missing arguments -> {}

    Handling both dict and object shapes is not paranoia: our own LLMResponse stores
    dicts, the raw SDK gives objects, and you will hit both.
    """
    # TODO: implement
    raise NotImplementedError


def tool_result_message(call: ToolCall, result: ToolResult) -> Message:
    """Build the `role: tool` message carrying one result back.

    Exact shape — all four keys:
        {"role": "tool", "tool_call_id": call.id, "name": call.name,
         "content": result.content}

    `tool_call_id` is how the model pairs this answer with its question. With one tool
    in flight you can get away without it; with two you cannot.
    """
    # TODO: implement
    raise NotImplementedError


def execute_tool_calls(registry: ToolRegistry, calls: list[ToolCall]) -> list[Message]:
    """Run every call and return one tool message per call, in the same order.

    ONE MESSAGE PER CALL, ALWAYS — including for the ones that errored. A model that
    requested three tools and received two results will either hallucinate the third or
    the provider will reject the request outright.
    """
    # TODO: implement
    raise NotImplementedError
