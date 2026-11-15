"""SOLUTION — Chapter 12, Exercise 2."""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from .exercise_1_span import Span


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
