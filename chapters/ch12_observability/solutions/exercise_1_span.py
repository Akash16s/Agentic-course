"""SOLUTION — Chapter 12, Exercise 1."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


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
