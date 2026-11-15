"""Tracing — seeing inside a run.

Promoted from Chapter 12.

An eval tells you a case failed. A trace tells you WHY. Without one you are reading
a final answer and guessing at forty steps of reasoning you cannot see.

The model here is OpenTelemetry's, deliberately: spans, a parent/child tree,
attributes, events, a status. If you later swap this for real OTel, nothing about
how you think changes — only the import.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

# --------------------------------------------------------------------- spans


@dataclass
class Span:
    """One timed operation. Spans nest to form a tree."""

    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: str | None = None
    trace_id: str = ""
    kind: str = "internal"            # internal | llm | tool | agent | eval
    start_time: float = 0.0
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"                # ok | error
    error: str | None = None

    @property
    def duration_s(self) -> float:
        if self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    @property
    def ended(self) -> bool:
        return self.end_time is not None

    def set(self, **attributes: Any) -> "Span":
        """Attach attributes. Chainable."""
        self.attributes.update(attributes)
        return self

    def event(self, name: str, **attributes: Any) -> "Span":
        """A point-in-time note inside the span — a retry, a cache hit, a decision."""
        self.events.append({"name": name, "at": time.time(), **attributes})
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "trace_id": self.trace_id,
            "kind": self.kind,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_s": round(self.duration_s, 6),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error": self.error,
        }


# -------------------------------------------------------------------- tracer


class Tracer:
    """Collects spans for one trace, tracking parentage automatically.

    The current span is held in thread-local state, so a span opened inside another
    becomes its child with no plumbing. That is what makes instrumentation a
    one-line `with` rather than passing a parent id through every function.
    """

    def __init__(self, *, trace_id: str | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.clock = clock
        self.spans: list[Span] = []
        self._local = threading.local()
        self._lock = threading.Lock()

    # ------------------------------------------------------------ current

    @property
    def current(self) -> Span | None:
        return getattr(self._local, "current", None)

    def _push(self, span: Span) -> None:
        stack = getattr(self._local, "stack", None)
        if stack is None:
            stack = self._local.stack = []
        stack.append(span)
        self._local.current = span

    def _pop(self) -> None:
        stack = getattr(self._local, "stack", [])
        if stack:
            stack.pop()
        self._local.current = stack[-1] if stack else None

    # -------------------------------------------------------------- span

    @contextmanager
    def span(self, name: str, *, kind: str = "internal",
             **attributes: Any) -> Iterator[Span]:
        """Open a span. Closes on exit, even when the body raises.

        >>> with tracer.span("agent.run", kind="agent") as s:
        ...     s.set(model="haiku")
        """
        span = Span(
            name=name,
            parent_id=self.current.span_id if self.current else None,
            trace_id=self.trace_id,
            kind=kind,
            start_time=self.clock(),
            attributes=dict(attributes),
        )
        with self._lock:
            self.spans.append(span)
        self._push(span)
        try:
            yield span
        except Exception as exc:
            # record the failure, then let it propagate. A tracer that swallows
            # exceptions is a tracer that causes outages.
            span.status = "error"
            span.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            span.end_time = self.clock()
            self._pop()

    # ------------------------------------------------------------ reading

    @property
    def root_spans(self) -> list[Span]:
        return [s for s in self.spans if s.parent_id is None]

    def children_of(self, span_id: str) -> list[Span]:
        return [s for s in self.spans if s.parent_id == span_id]

    def total_duration(self) -> float:
        return sum(s.duration_s for s in self.root_spans)

    def sum_attribute(self, key: str) -> float:
        """Add up a numeric attribute across every span — cost, tokens, retries."""
        total = 0.0
        for span in self.spans:
            value = span.attributes.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total += float(value)
        return total

    def errors(self) -> list[Span]:
        return [s for s in self.spans if s.status == "error"]

    def slowest(self, n: int = 5) -> list[Span]:
        return sorted(self.spans, key=lambda s: -s.duration_s)[:n]

    # ------------------------------------------------------------- output

    def render(self, *, show_attributes: bool = True) -> str:
        """The span tree as indented text. The thing you actually read."""
        lines: list[str] = []

        def walk(span: Span, depth: int) -> None:
            marker = "x" if span.status == "error" else "-"
            lines.append(
                f"{'  ' * depth}{marker} {span.name} "
                f"[{span.kind}] {span.duration_s * 1000:.0f}ms"
            )
            if span.error:
                lines.append(f"{'  ' * depth}    ! {span.error}")
            if show_attributes and span.attributes:
                shown = ", ".join(f"{k}={_short(v)}" for k, v in span.attributes.items())
                lines.append(f"{'  ' * depth}    {shown}")
            for event in span.events:
                lines.append(f"{'  ' * depth}    * {event['name']}")
            for child in self.children_of(span.span_id):
                walk(child, depth + 1)

        for root in self.root_spans:
            walk(root, 0)
        return "\n".join(lines)

    def summary(self) -> str:
        cost = self.sum_attribute("cost_usd")
        tokens = self.sum_attribute("total_tokens")
        return (
            f"trace {self.trace_id}: {len(self.spans)} spans, "
            f"{self.total_duration():.2f}s, ${cost:.4f}, {tokens:.0f} tokens, "
            f"{len(self.errors())} error(s)"
        )

    def to_jsonl(self, path: str) -> None:
        """Append every span as one JSON line.

        Append, not overwrite, and one line per span: that is what lets you `cat`
        a week of traces together, grep them, and load them into anything.
        """
        with open(path, "a", encoding="utf-8") as handle:
            for span in self.spans:
                handle.write(json.dumps(span.to_dict()) + "\n")


def _short(value: Any, limit: int = 60) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


# ------------------------------------------------------- instrumented client


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
            span.set(tool=name, arguments=_short(arguments, 200))
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
