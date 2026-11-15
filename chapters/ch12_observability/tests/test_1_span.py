"""Tests for Chapter 12, Exercise 1 — the Span."""

import json

import pytest

from chapters.ch12_observability.exercises.exercise_1_span import Span


class TestFields:
    def test_defaults(self):
        s = Span(name="x")
        assert s.parent_id is None
        assert s.kind == "internal"
        assert s.status == "ok"
        assert s.error is None
        assert s.attributes == {}
        assert s.events == []

    def test_generates_a_span_id(self):
        assert Span(name="x").span_id
        assert Span(name="x").span_id != Span(name="y").span_id

    def test_defaults_are_not_shared(self):
        a, b = Span(name="a"), Span(name="b")
        a.attributes["k"] = 1
        a.events.append({"name": "e"})
        assert b.attributes == {} and b.events == []


class TestDuration:
    def test_computed(self):
        s = Span(name="x", start_time=100.0, end_time=100.5)
        assert s.duration_s == pytest.approx(0.5)

    def test_open_span_is_zero_not_an_error(self):
        # unfinished spans appear in the tree whenever you look at a live run
        assert Span(name="x", start_time=100.0).duration_s == 0.0

    def test_ended(self):
        assert not Span(name="x", start_time=1.0).ended
        assert Span(name="x", start_time=1.0, end_time=2.0).ended


class TestAttributes:
    def test_set(self):
        s = Span(name="x").set(model="haiku", tokens=100)
        assert s.attributes == {"model": "haiku", "tokens": 100}

    def test_set_merges(self):
        s = Span(name="x").set(a=1).set(b=2)
        assert s.attributes == {"a": 1, "b": 2}

    def test_set_overwrites(self):
        assert Span(name="x").set(a=1).set(a=2).attributes["a"] == 2

    def test_set_chains(self):
        s = Span(name="x")
        assert s.set(a=1) is s


class TestEvents:
    def test_event(self):
        s = Span(name="x").event("retry", attempt=2)
        assert len(s.events) == 1
        assert s.events[0]["name"] == "retry"
        assert s.events[0]["attempt"] == 2
        assert s.events[0]["at"] > 0

    def test_events_keep_order(self):
        s = Span(name="x").event("first").event("second")
        assert [e["name"] for e in s.events] == ["first", "second"]

    def test_event_chains(self):
        s = Span(name="x")
        assert s.event("a") is s


class TestToDict:
    def test_has_every_field(self):
        d = Span(name="x", kind="llm", start_time=1.0, end_time=2.0).to_dict()
        for key in ("name", "span_id", "parent_id", "trace_id", "kind",
                    "start_time", "end_time", "duration_s", "attributes",
                    "events", "status", "error"):
            assert key in d

    def test_includes_computed_duration(self):
        d = Span(name="x", start_time=1.0, end_time=1.25).to_dict()
        assert d["duration_s"] == pytest.approx(0.25)

    def test_json_serialisable(self):
        s = Span(name="x", kind="tool", start_time=1.0, end_time=2.0)
        s.set(model="haiku", cost=0.001).event("retry")
        json.dumps(s.to_dict())   # a span that cannot serialise is a lost trace

    def test_round_trips_attributes(self):
        d = Span(name="x").set(a=1, b="two").to_dict()
        assert d["attributes"] == {"a": 1, "b": "two"}
