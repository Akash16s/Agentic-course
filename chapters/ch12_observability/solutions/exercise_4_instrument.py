"""SOLUTION — Chapter 12, Exercise 4."""

from __future__ import annotations

from typing import Any

from .exercise_2_tracer import Tracer
from .exercise_3_analysis import short


class TracedClient:
    """Wraps an LLM client so every call becomes a span.

    A decorator, not a subclass: it works with `LLMClient`, `FakeLLMClient`, or
    anything else with a `chat` method. That is why the whole of Chapter 12 can be
    tested without a network.
    """

    def __init__(self, inner: Any, tracer: Tracer) -> None:
        self.inner = inner
        self.tracer = tracer

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        with self.tracer.span("llm.chat", kind="llm") as span:
            span.set(
                model=kwargs.get("model") or getattr(self.inner, "model", "unknown"),
                messages=len(messages),
                temperature=kwargs.get("temperature"),
            )
            response = self.inner.chat(messages, **kwargs)
            usage = getattr(response, "usage", None)
            if usage is not None:
                span.set(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )
                try:
                    from agentlib.pricing import cost_usd

                    span.set(cost_usd=cost_usd(
                        getattr(response, "model", "") or "",
                        usage.prompt_tokens, usage.completion_tokens))
                except Exception:  # noqa: BLE001 - pricing must never break a call
                    pass
            span.set(finish_reason=getattr(response, "finish_reason", None),
                     tool_calls=len(getattr(response, "tool_calls", []) or []))
            return response

    def stream_raw(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        return self.inner.stream_raw(messages, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


class TracedRegistry:
    """Wraps a ToolRegistry so every tool execution becomes a span.

    Tool spans are often where the time actually goes, and an untraced tool layer
    makes an agent look like it spent 8 seconds "thinking" when it spent 7.5 of
    them waiting on one HTTP call.
    """

    def __init__(self, inner: Any, tracer: Tracer) -> None:
        self.inner = inner
        self.tracer = tracer

    def execute(self, name: str, arguments: Any) -> Any:
        with self.tracer.span(f"tool.{name}", kind="tool") as span:
            span.set(tool=name, arguments=short(arguments, 200))
            result = self.inner.execute(name, arguments)
            span.set(
                is_error=getattr(result, "is_error", False),
                result_chars=len(getattr(result, "content", "") or ""),
            )
            if getattr(result, "is_error", False):
                span.status = "error"
                span.error = getattr(result, "content", "")
            return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)
