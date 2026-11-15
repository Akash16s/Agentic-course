"""Tests for Chapter 8, Exercise 1 — the blackboard."""

import threading

import pytest

from chapters.ch08_multi_agent.exercises.exercise_1_blackboard import Blackboard, Entry


class TestBasics:
    def test_write_and_read(self):
        b = Blackboard()
        b.write("topic", "pricing", by="planner")
        assert b.read("topic") == "pricing"

    def test_missing_key(self):
        assert Blackboard().read("nope") is None
        assert Blackboard().read("nope", "fallback") == "fallback"

    def test_has(self):
        b = Blackboard()
        b.write("k", 1)
        assert b.has("k")
        assert not b.has("other")

    def test_all_returns_a_copy(self):
        b = Blackboard()
        b.write("k", 1)
        b.all()["k"] = 999
        assert b.read("k") == 1

    def test_overwrite_is_allowed(self):
        b = Blackboard()
        b.write("k", 1)
        b.write("k", 2)
        assert b.read("k") == 2

    def test_stores_any_type(self):
        b = Blackboard()
        b.write("list", [1, 2])
        b.write("dict", {"a": 1})
        assert b.read("list") == [1, 2]
        assert b.read("dict") == {"a": 1}


class TestLog:
    def test_every_write_is_logged(self):
        b = Blackboard()
        b.write("a", 1, by="x")
        b.write("b", 2, by="y")
        assert len(b.log) == 2

    def test_log_records_the_author(self):
        b = Blackboard()
        b.write("a", 1, by="researcher")
        assert b.log[0].by == "researcher"

    def test_default_author(self):
        b = Blackboard()
        b.write("a", 1)
        assert b.log[0].by == "unknown"

    def test_log_is_append_only_across_overwrites(self):
        b = Blackboard()
        b.write("k", 1, by="a")
        b.write("k", 2, by="b")
        assert len(b.log) == 2
        assert [e.value for e in b.log] == [1, 2]

    def test_log_returns_a_copy(self):
        b = Blackboard()
        b.write("k", 1)
        b.log.clear()
        assert len(b.log) == 1

    def test_entries_are_timestamped(self):
        b = Blackboard()
        b.write("k", 1)
        assert b.log[0].at > 0

    def test_history_of_one_key(self):
        b = Blackboard()
        b.write("k", 1, by="a")
        b.write("other", 9, by="c")
        b.write("k", 2, by="b")
        history = b.history("k")
        assert [(e.by, e.value) for e in history] == [("a", 1), ("b", 2)]

    def test_history_reveals_agents_fighting(self):
        # the characteristic blackboard bug: invisible in the final state
        b = Blackboard()
        b.write("summary", "version A", by="writer")
        b.write("summary", "version B", by="editor")
        b.write("summary", "version A again", by="writer")
        assert b.read("summary") == "version A again"
        authors = [e.by for e in b.history("summary")]
        assert authors == ["writer", "editor", "writer"]

    def test_history_of_an_unknown_key(self):
        assert Blackboard().history("nope") == []


class TestRender:
    def test_empty(self):
        assert "nothing" in Blackboard().render().lower()

    def test_lists_keys_and_values(self):
        b = Blackboard()
        b.write("topic", "pricing")
        out = b.render()
        assert "topic" in out and "pricing" in out

    def test_truncates_long_values(self):
        b = Blackboard()
        b.write("doc", "x" * 50_000)
        assert len(b.render(max_chars=100)) < 300, "render() goes into a context window"


class TestThreadSafety:
    def test_concurrent_writes_are_all_logged(self):
        b = Blackboard()

        def work(i):
            for j in range(20):
                b.write(f"k{i}-{j}", j, by=f"agent{i}")

        threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(b.log) == 160, "writes were lost to a race"
        assert len(b.all()) == 160
