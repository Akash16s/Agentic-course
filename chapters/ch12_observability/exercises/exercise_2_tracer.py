"""EXERCISE 2 — The Tracer.

    pytest chapters/ch12_observability/tests -q -k tracer
"""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from .exercise_1_span import Span


class Tracer:
    """Collects spans for one trace, tracking parentage automatically.

    __init__(self, *, trace_id: str | None = None, clock=time.time)
        trace_id defaults to uuid4().hex[:16]
        self.spans: list[Span]
        a threading.local() for the open-span stack
        a threading.Lock for appending to self.spans
    """

    def __init__(self, *, trace_id: str | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        # TODO: implement
        raise NotImplementedError

    @property
    def current(self) -> Span | None:
        """The innermost open span ON THIS THREAD, or None."""
        # TODO: implement
        raise NotImplementedError

    def _push(self, span: Span) -> None:
        """Push onto this thread's stack and set `current`.

        Lazily create the stack: `getattr(self._local, "stack", None)` and assign
        if missing. threading.local() attributes do not exist until set, per thread.
        """
        # TODO: implement
        raise NotImplementedError

    def _pop(self) -> None:
        """Pop this thread's stack; `current` becomes the new top, or None."""
        # TODO: implement
        raise NotImplementedError

    @contextmanager
    def span(self, name: str, *, kind: str = "internal",
             **attributes: Any) -> Iterator[Span]:
        """Open a span; close it on exit, EVEN IF THE BODY RAISES.

        Spec:
          1. build a Span with
                 parent_id = self.current.span_id if self.current else None
                 trace_id  = self.trace_id
                 start_time = self.clock()
                 attributes = dict(attributes)
          2. append it to self.spans (under the lock) and push it
          3. yield the span
          4. on an exception:
                 span.status = "error"
                 span.error  = f"{type(exc).__name__}: {exc}"
                 RE-RAISE.
          5. in a `finally`: set end_time and pop

        TWO THINGS THAT MATTER MORE THAN THE REST:

        RE-RAISE. A tracer that swallows exceptions is a tracer that causes
        outages. Record, then let it fly.

        THREAD-LOCAL, not a plain attribute. Chapter 3 runs tools in a thread pool;
        with shared state two parallel tools fight over "the current span" and the
        tree comes out nonsense — nested wrongly, or with cycles. (This same
        approach breaks under asyncio, where many tasks share one thread. The async
        answer is contextvars.ContextVar, which is what real OTel uses.)
        """
        # TODO: implement
        raise NotImplementedError
