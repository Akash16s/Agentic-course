"""EXERCISE 4 — Instrumenting without touching the code.

    pytest chapters/ch12_observability/tests -q -k instrument
"""

from __future__ import annotations

from typing import Any

from .exercise_2_tracer import Tracer
from .exercise_3_analysis import short


class TracedClient:
    """Wrap an LLM client so every `chat` becomes a span.

    A WRAPPER, NOT A SUBCLASS. `__getattr__` delegates everything else to the inner
    object, so this is a drop-in for LLMClient, FakeLLMClient, or anything else with
    a `chat` method — which is exactly why this chapter is testable offline.

    chat(messages, **kwargs):
      open a span named "llm.chat", kind="llm", and set:
        before the call:  model (kwargs["model"] or inner.model or "unknown"),
                          messages (the COUNT, not the content — see the chapter on
                          what never to log), temperature
        after the call:   prompt_tokens, completion_tokens, total_tokens from
                          response.usage when present;
                          cost_usd via agentlib.pricing.cost_usd — wrapped in
                          try/except, because a pricing lookup must NEVER break a
                          working API call;
                          finish_reason, and tool_calls (the count)
      return the response.
    """

    def __init__(self, inner: Any, tracer: Tracer) -> None:
        # TODO: implement
        raise NotImplementedError

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        # TODO: implement
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        """Delegate anything we do not override.

        Careful: `__getattr__` is called for MISSING attributes, so it must not
        reference `self.inner` before `__init__` has set it, or you get infinite
        recursion on an unpickling or a copy. Setting `inner` first in `__init__`
        is enough here.
        """
        # TODO: implement
        raise NotImplementedError


class TracedRegistry:
    """Wrap a ToolRegistry so every execution becomes a span.

    execute(name, arguments):
      span f"tool.{name}", kind="tool"
        before: tool=name, arguments=short(arguments, 200)
        after:  is_error, result_chars (len of result.content)
        if the result is an error: set span.status = "error" and span.error
      return the result unchanged.

    TRACE THE TOOL LAYER. Without it an agent looks like it spent 8 seconds
    thinking when it spent 7.5 of them waiting on one HTTP call — and you go off
    optimising prompts while the actual problem is a slow API.

    Note the tool's ERROR becomes a span error, but `execute` still RETURNS
    normally. Chapter 2's rule stands: tool failures are data for the model. The
    span error is for you.
    """

    def __init__(self, inner: Any, tracer: Tracer) -> None:
        # TODO: implement
        raise NotImplementedError

    def execute(self, name: str, arguments: Any) -> Any:
        # TODO: implement
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        # TODO: implement
        raise NotImplementedError
