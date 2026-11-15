"""EXERCISE 3 — Parallel tool execution.

WHY: Models routinely ask for 3-5 independent tools at once. Running them serially
multiplies your latency for nothing. Running them wrong corrupts the conversation.

    pytest chapters/ch03_react_loop/tests -q -k parallel
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from agentlib.llm import Message
from agentlib.tools import ToolCall, ToolRegistry, tool_result_message

#: Never open more than this many threads, however many tools the model asks for.
MAX_WORKERS = 8


def run_tools(
    registry: ToolRegistry,
    calls: list[ToolCall],
    *,
    parallel: bool = True,
) -> list[Message]:
    """Execute every call and return one tool message per call, IN INPUT ORDER.

    Spec:
      * [] -> []
      * not parallel, or exactly one call -> run serially (no thread pool: spinning one
        up for a single call is pure overhead)
      * otherwise -> ThreadPoolExecutor with min(MAX_WORKERS, len(calls)) workers

    ORDER IS PART OF THE CONTRACT. `pool.map` preserves input order; `as_completed`
    does not. Use map.

    Threads rather than asyncio because tools are blocking I/O — file reads, HTTP with
    `requests`, database drivers. Chapter 15 does the async version.

    IMPORTANT: a `StopSignal` raised inside a tool must propagate out of this function,
    not be caught. It is control flow, not an error. (`Tool.call` already re-raises it;
    make sure you do not add a try/except that swallows it. With a thread pool, an
    exception inside a worker surfaces when you consume the result — which `list()`
    does, so this works naturally.)
    """
    # TODO: implement
    raise NotImplementedError
