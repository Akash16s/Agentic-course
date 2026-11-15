"""Tests for Chapter 5, Exercise 3 — FullHistory and SlidingWindow."""

import pytest

from chapters.ch05_short_term_memory.exercises.exercise_3_strategies import (
    FullHistory,
    MemoryStrategy,
    SlidingWindow,
)


def msgs(n=20, size=200):
    return [{"role": "user", "content": f"turn {i} " + "x" * size} for i in range(n)]


class TestInterface:
    def test_abstract(self):
        with pytest.raises(TypeError):
            MemoryStrategy()


class TestFullHistory:
    def test_returns_everything(self):
        m = msgs(10)
        assert FullHistory().build(m) == m

    def test_returns_a_copy(self):
        m = msgs(3)
        out = FullHistory().build(m)
        out.append({"role": "user", "content": "extra"})
        assert len(m) == 3, "strategies must not hand back their input list"

    def test_empty(self):
        assert FullHistory().build([]) == []


class TestSlidingWindow:
    def test_trims_to_budget(self):
        out = SlidingWindow(max_tokens=200, keep_first=0, keep_last=1).build(msgs(20))
        assert len(out) < 20

    def test_keeps_the_task_statement_by_default(self):
        m = [{"role": "user", "content": "THE TASK: migrate the database"}] + msgs(20)
        out = SlidingWindow(max_tokens=150).build(m)
        assert "THE TASK" in out[0]["content"], (
            "keep_first defaults to 1 so the agent does not forget its objective"
        )

    def test_keeps_recent_turns(self):
        out = SlidingWindow(max_tokens=200, keep_last=3).build(msgs(20))
        assert "turn 19" in out[-1]["content"]

    def test_short_history_untouched(self):
        m = msgs(2, size=10)
        assert SlidingWindow(max_tokens=10_000).build(m) == m

    def test_keep_last_is_honoured_even_over_budget(self):
        out = SlidingWindow(max_tokens=1, keep_first=0, keep_last=3).build(msgs(20))
        assert len(out) == 3

    def test_does_not_split_tool_groups(self):
        m = []
        for i in range(8):
            m += [
                {"role": "user", "content": "x" * 200},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"c{i}", "type": "function",
                     "function": {"name": "t", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": f"c{i}", "name": "t", "content": "r"},
            ]
        out = SlidingWindow(max_tokens=200, keep_first=0, keep_last=2).build(m)
        for i, message in enumerate(out):
            if message["role"] == "tool":
                assert i > 0 and out[i - 1].get("tool_calls")
