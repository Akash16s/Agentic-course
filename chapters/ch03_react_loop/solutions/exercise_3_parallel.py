"""SOLUTION — Chapter 3, Exercise 3."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from agentlib.llm import Message
from agentlib.tools import ToolCall, ToolRegistry, tool_result_message

MAX_WORKERS = 8


def run_tools(
    registry: ToolRegistry,
    calls: list[ToolCall],
    *,
    parallel: bool = True,
) -> list[Message]:
    if not calls:
        return []

    def run_one(call: ToolCall) -> Message:
        return tool_result_message(call, registry.execute(call.name, call.arguments))

    if not parallel or len(calls) == 1:
        return [run_one(call) for call in calls]

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(calls))) as pool:
        # map() preserves input order; as_completed() would not.
        # list() consumes the iterator here, so a StopSignal from a worker surfaces
        # inside the `with` block and propagates to the caller, as intended.
        return list(pool.map(run_one, calls))
