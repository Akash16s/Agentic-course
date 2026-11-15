"""EXERCISE 1 — The Span.

    pytest chapters/ch12_observability/tests -q -k span
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Span:
    """One timed operation.

    Fields:
        name: str
        span_id: str        = uuid4().hex[:12]
        parent_id: str|None = None
        trace_id: str       = ""
        kind: str           = "internal"   # internal | llm | tool | agent | eval
        start_time: float   = 0.0
        end_time: float|None= None
        attributes: dict    = {}
        events: list[dict]  = []
        status: str         = "ok"         # ok | error
        error: str|None     = None
    """

    name: str

    @property
    def duration_s(self) -> float:
        """end - start, or 0.0 while the span is still open.

        0.0 rather than raising: an unfinished span turns up in a rendered tree all
        the time (you are looking at a trace of a run that is still going), and a
        renderer that throws on one is useless exactly then.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def ended(self) -> bool:
        # TODO: implement
        raise NotImplementedError

    def set(self, **attributes: Any) -> "Span":
        """Merge attributes in. Return self so calls chain."""
        # TODO: implement
        raise NotImplementedError

    def event(self, name: str, **attributes: Any) -> "Span":
        """Append {"name": name, "at": time.time(), **attributes}. Return self.

        Events are points in TIME inside a span — a retry fired, a cache hit, a
        decision taken. Attributes are facts ABOUT the span. Using attributes for
        things that happen loses the ordering.
        """
        # TODO: implement
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """A JSON-serialisable dict with every field, plus a computed
        "duration_s" rounded to 6 places.

        Must survive `json.dumps`. This is the JSONL export format, and a span that
        cannot serialise is a trace you cannot store.
        """
        # TODO: implement
        raise NotImplementedError
