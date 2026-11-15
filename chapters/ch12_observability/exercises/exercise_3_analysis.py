"""EXERCISE 3 — Reading a trace.

Add these as methods on YOUR Tracer from Exercise 2 (this module subclasses it so
the tests can find them in one place).

    pytest chapters/ch12_observability/tests -q -k analysis
"""

from __future__ import annotations

import json
from typing import Any

from .exercise_1_span import Span
from .exercise_2_tracer import Tracer


def short(value: Any, limit: int = 60) -> str:
    """str(value), truncated with '...' if longer than `limit`."""
    # TODO: implement
    raise NotImplementedError


class AnalysingTracer(Tracer):
    """Tracer + the reading methods."""

    @property
    def root_spans(self) -> list[Span]:
        """Spans with no parent."""
        # TODO: implement
        raise NotImplementedError

    def children_of(self, span_id: str) -> list[Span]:
        """Direct children, in creation order."""
        # TODO: implement
        raise NotImplementedError

    def total_duration(self) -> float:
        """Sum of the ROOT spans' durations.

        Roots only. Summing every span double-counts: a child's time is already
        inside its parent's, and with nesting three deep you get a number several
        times the wall clock.
        """
        # TODO: implement
        raise NotImplementedError

    def sum_attribute(self, key: str) -> float:
        """Add up a numeric attribute across ALL spans (cost_usd, total_tokens...).

        Skip non-numeric values, and skip bools — `isinstance(True, int)` is True
        in Python, and silently adding 1 for every `is_error=True` would be a
        wonderfully confusing bug.
        """
        # TODO: implement
        raise NotImplementedError

    def errors(self) -> list[Span]:
        # TODO: implement
        raise NotImplementedError

    def slowest(self, n: int = 5) -> list[Span]:
        """The n longest spans, longest first."""
        # TODO: implement
        raise NotImplementedError

    def render(self, *, show_attributes: bool = True) -> str:
        """The span tree as indented text. The thing you actually read.

        Suggested shape (two spaces per level):

            - agent.run [agent] 4210ms
                task=find the bug, steps=6
                * step
              - llm.chat [llm] 890ms
                  model=haiku, total_tokens=1204
              x tool.search [tool] 2100ms
                  ! ConnectionError: timed out

        '-' for ok, 'x' for error; '!' for the error text; '*' for events.
        Truncate attribute values with `short` — a 50k-token prompt in a rendered
        tree is not a trace, it is a wall.
        """
        # TODO: implement
        raise NotImplementedError

    def summary(self) -> str:
        """One line: trace id, span count, total duration, summed cost_usd,
        summed total_tokens, error count."""
        # TODO: implement
        raise NotImplementedError

    def to_jsonl(self, path: str) -> None:
        """APPEND one `json.dumps(span.to_dict())` per line.

        Append, not overwrite, and one line per span. That is what lets you `cat` a
        week of traces together, grep for a trace id, and load them into jq, DuckDB
        or anything else. Do not invent a format.
        """
        # TODO: implement
        raise NotImplementedError
