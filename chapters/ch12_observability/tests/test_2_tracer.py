"""Tests for Chapter 12, Exercise 2 — the Tracer."""

import threading
import time

import pytest

from chapters.ch12_observability.exercises.exercise_2_tracer import Tracer


class TestBasics:
    def test_generates_a_trace_id(self):
        assert Tracer().trace_id

    def test_explicit_trace_id(self):
        assert Tracer(trace_id="abc").trace_id == "abc"

    def test_no_spans_initially(self):
        t = Tracer()
        assert t.spans == []
        assert t.current is None

    def test_span_is_recorded(self):
        t = Tracer()
        with t.span("work"):
            pass
        assert len(t.spans) == 1
        assert t.spans[0].name == "work"

    def test_span_gets_the_trace_id(self):
        t = Tracer(trace_id="abc")
        with t.span("work"):
            pass
        assert t.spans[0].trace_id == "abc"

    def test_kind_and_attributes(self):
        t = Tracer()
        with t.span("llm.chat", kind="llm", model="haiku"):
            pass
        assert t.spans[0].kind == "llm"
        assert t.spans[0].attributes["model"] == "haiku"

    def test_span_is_closed_on_exit(self):
        t = Tracer()
        with t.span("work") as s:
            assert not s.ended
        assert s.ended
        assert s.duration_s >= 0

    def test_duration_is_measured(self):
        t = Tracer()
        with t.span("slow"):
            time.sleep(0.02)
        assert t.spans[0].duration_s >= 0.015

    def test_injected_clock(self):
        ticks = iter([100.0, 100.5])
        t = Tracer(clock=lambda: next(ticks))
        with t.span("work"):
            pass
        assert t.spans[0].duration_s == pytest.approx(0.5)


class TestNesting:
    def test_child_gets_its_parent(self):
        t = Tracer()
        with t.span("parent") as p:
            with t.span("child") as c:
                pass
        assert c.parent_id == p.span_id

    def test_root_has_no_parent(self):
        t = Tracer()
        with t.span("root") as r:
            pass
        assert r.parent_id is None

    def test_three_deep(self):
        t = Tracer()
        with t.span("a") as a:
            with t.span("b") as b:
                with t.span("c") as c:
                    pass
        assert b.parent_id == a.span_id
        assert c.parent_id == b.span_id

    def test_siblings_share_a_parent(self):
        t = Tracer()
        with t.span("parent") as p:
            with t.span("one") as one:
                pass
            with t.span("two") as two:
                pass
        assert one.parent_id == two.parent_id == p.span_id

    def test_current_tracks_the_stack(self):
        t = Tracer()
        assert t.current is None
        with t.span("a") as a:
            assert t.current is a
            with t.span("b") as b:
                assert t.current is b
            assert t.current is a
        assert t.current is None

    def test_two_roots(self):
        t = Tracer()
        with t.span("one"):
            pass
        with t.span("two"):
            pass
        assert all(s.parent_id is None for s in t.spans)


class TestErrors:
    def test_exception_is_recorded(self):
        t = Tracer()
        with pytest.raises(ValueError):
            with t.span("work"):
                raise ValueError("boom")
        assert t.spans[0].status == "error"
        assert "ValueError" in t.spans[0].error
        assert "boom" in t.spans[0].error

    def test_exception_propagates(self):
        # a tracer that swallows exceptions causes outages
        t = Tracer()
        with pytest.raises(RuntimeError):
            with t.span("work"):
                raise RuntimeError("must escape")

    def test_span_is_still_closed_on_error(self):
        t = Tracer()
        with pytest.raises(ValueError):
            with t.span("work") as s:
                raise ValueError("x")
        assert s.ended

    def test_stack_unwinds_on_error(self):
        t = Tracer()
        with t.span("parent"):
            with pytest.raises(ValueError):
                with t.span("child"):
                    raise ValueError("x")
            assert t.current.name == "parent", "the stack was left corrupted"
        assert t.current is None

    def test_an_error_in_a_child_does_not_fail_the_parent(self):
        t = Tracer()
        with t.span("parent") as p:
            try:
                with t.span("child"):
                    raise ValueError("x")
            except ValueError:
                pass
        assert p.status == "ok"


class TestThreadSafety:
    def test_parallel_spans_do_not_corrupt_the_tree(self):
        # Chapter 3 runs tools in a thread pool; with shared state these interleave
        # and the tree comes out nonsense
        t = Tracer()
        results = []

        def work(i):
            with t.span(f"root-{i}") as root:
                time.sleep(0.01)
                with t.span(f"child-{i}") as child:
                    results.append((root.span_id, child.parent_id))

        threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(results) == 8
        for root_id, parent_id in results:
            assert parent_id == root_id, "a child was attached to another thread's span"

    def test_all_spans_are_recorded_under_concurrency(self):
        t = Tracer()

        def work(i):
            with t.span(f"s{i}"):
                pass

        threads = [threading.Thread(target=work, args=(i,)) for i in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert len(t.spans) == 20, "spans were lost to a race on the list"
