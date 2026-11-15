"""SOLUTION — Chapter 12, Exercise 3."""

from __future__ import annotations

import json
from typing import Any

from .exercise_1_span import Span
from .exercise_2_tracer import Tracer


def short(value: Any, limit: int = 60) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class AnalysingTracer(Tracer):
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
                shown = ", ".join(f"{k}={short(v)}" for k, v in span.attributes.items())
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


def short(value: Any, limit: int = 60) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
