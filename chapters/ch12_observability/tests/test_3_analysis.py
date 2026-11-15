"""Tests for Chapter 12, Exercise 3 — reading a trace."""

import json

import pytest

from chapters.ch12_observability.exercises.exercise_3_analysis import (
    AnalysingTracer,
    short,
)


def build():
    # agent.run 0.0-3.0 | llm.chat 0.1-0.2 | tool.search 0.4-2.4 | llm.chat 2.5-2.6
    ticks = iter([0.0, 0.1, 0.2, 0.4, 2.4, 2.5, 2.6, 3.0])
    t = AnalysingTracer(trace_id="t1", clock=lambda: next(ticks))
    with t.span("agent.run", kind="agent", task="find the bug") as root:
        root.event("step", index=0)
        with t.span("llm.chat", kind="llm") as a:
            a.set(cost_usd=0.001, total_tokens=500)
        with t.span("tool.search", kind="tool") as tool:
            tool.set(cost_usd=0.0)
        with t.span("llm.chat", kind="llm") as b:
            b.set(cost_usd=0.010, total_tokens=5000)
    return t


class TestShort:
    def test_leaves_short_values(self):
        assert short("hello") == "hello"

    def test_truncates(self):
        assert len(short("x" * 500, 60)) == 60
        assert short("x" * 500, 60).endswith("...")

    def test_stringifies(self):
        assert short(42) == "42"


class TestStructure:
    def test_root_spans(self):
        t = build()
        assert [s.name for s in t.root_spans] == ["agent.run"]

    def test_children_of(self):
        t = build()
        root = t.root_spans[0]
        assert [s.name for s in t.children_of(root.span_id)] == [
            "llm.chat", "tool.search", "llm.chat"
        ]

    def test_leaf_has_no_children(self):
        t = build()
        leaf = [s for s in t.spans if s.name == "tool.search"][0]
        assert t.children_of(leaf.span_id) == []

    def test_total_duration_counts_roots_only(self):
        # summing every span double-counts: a child's time is inside its parent's
        t = build()
        assert t.total_duration() == pytest.approx(t.root_spans[0].duration_s)
        assert t.total_duration() < sum(s.duration_s for s in t.spans)


class TestAggregation:
    def test_sum_attribute(self):
        assert build().sum_attribute("cost_usd") == pytest.approx(0.011)

    def test_sum_tokens(self):
        assert build().sum_attribute("total_tokens") == pytest.approx(5500)

    def test_missing_attribute_sums_to_zero(self):
        assert build().sum_attribute("nonexistent") == 0.0

    def test_ignores_non_numeric_values(self):
        t = AnalysingTracer()
        with t.span("a") as s:
            s.set(value="not a number")
        assert t.sum_attribute("value") == 0.0

    def test_ignores_bools(self):
        # isinstance(True, int) is True; silently adding 1 per is_error would be
        # a wonderfully confusing bug
        t = AnalysingTracer()
        with t.span("a") as s:
            s.set(is_error=True)
        with t.span("b") as s:
            s.set(is_error=True)
        assert t.sum_attribute("is_error") == 0.0


class TestFinding:
    def test_errors(self):
        t = AnalysingTracer()
        with t.span("ok"):
            pass
        with pytest.raises(ValueError):
            with t.span("bad"):
                raise ValueError("x")
        assert [s.name for s in t.errors()] == ["bad"]

    def test_no_errors(self):
        assert build().errors() == []

    def test_slowest(self):
        t = build()
        assert t.slowest(1)[0].name == "agent.run"

    def test_slowest_is_sorted(self):
        durations = [s.duration_s for s in build().slowest(4)]
        assert durations == sorted(durations, reverse=True)

    def test_slowest_respects_n(self):
        assert len(build().slowest(2)) == 2

    def test_slowest_finds_the_slow_tool(self):
        t = build()
        names = [s.name for s in t.slowest(2)]
        assert "tool.search" in names, "the slow tool should stand out"


class TestRender:
    def test_shows_every_span(self):
        out = build().render()
        for name in ("agent.run", "llm.chat", "tool.search"):
            assert name in out

    def test_indents_children(self):
        lines = build().render().splitlines()
        root_line = next(l for l in lines if "agent.run" in l)
        child_line = next(l for l in lines if "llm.chat" in l)
        assert len(child_line) - len(child_line.lstrip()) > (
            len(root_line) - len(root_line.lstrip())
        )

    def test_shows_durations(self):
        assert "ms" in build().render()

    def test_shows_kinds(self):
        out = build().render()
        assert "[llm]" in out and "[tool]" in out

    def test_shows_attributes(self):
        assert "find the bug" in build().render()

    def test_attributes_can_be_hidden(self):
        assert "find the bug" not in build().render(show_attributes=False)

    def test_shows_events(self):
        assert "step" in build().render()

    def test_marks_errors(self):
        t = AnalysingTracer()
        with pytest.raises(ValueError):
            with t.span("bad"):
                raise ValueError("boom")
        out = t.render()
        assert "x " in out
        assert "boom" in out

    def test_truncates_huge_attributes(self):
        t = AnalysingTracer()
        with t.span("a") as s:
            s.set(prompt="x" * 50_000)
        assert len(t.render()) < 1_000, "a rendered tree is for reading"


class TestOutput:
    def test_summary(self):
        out = build().summary()
        assert "t1" in out
        assert "4" in out          # span count
        assert "0.011" in out or "0.0110" in out

    def test_summary_counts_errors(self):
        t = AnalysingTracer()
        with pytest.raises(ValueError):
            with t.span("bad"):
                raise ValueError("x")
        assert "1 error" in t.summary()

    def test_jsonl_one_line_per_span(self, tmp_path):
        path = str(tmp_path / "trace.jsonl")
        t = build()
        t.to_jsonl(path)
        with open(path) as handle:
            lines = [l for l in handle if l.strip()]
        assert len(lines) == 4
        for line in lines:
            json.loads(line)

    def test_jsonl_appends(self, tmp_path):
        # append, so you can cat a week of traces together
        path = str(tmp_path / "trace.jsonl")
        build().to_jsonl(path)
        build().to_jsonl(path)
        with open(path) as handle:
            assert len([l for l in handle if l.strip()]) == 8

    def test_jsonl_preserves_parentage(self, tmp_path):
        path = str(tmp_path / "trace.jsonl")
        t = build()
        t.to_jsonl(path)
        with open(path) as handle:
            rows = [json.loads(l) for l in handle if l.strip()]
        roots = [r for r in rows if r["parent_id"] is None]
        assert len(roots) == 1
        assert all(r["parent_id"] == roots[0]["span_id"]
                   for r in rows if r is not roots[0])
