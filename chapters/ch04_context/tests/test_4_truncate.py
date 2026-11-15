"""Tests for Chapter 4, Exercise 4 — bounding tool output."""

from chapters.ch04_context.exercises.exercise_4_truncate import (
    middle_out,
    truncate_tool_results,
)


class TestMiddleOut:
    def test_short_text_untouched(self):
        assert middle_out("hello", 100) == "hello"

    def test_exact_length_untouched(self):
        assert middle_out("x" * 50, 50) == "x" * 50

    def test_never_exceeds_max_chars(self):
        for n in (5, 10, 30, 60, 200, 1000):
            assert len(middle_out("x" * 5000, n)) <= n

    def test_keeps_head_and_tail(self):
        text = "START" + "M" * 500 + "END"
        out = middle_out(text, 80)
        assert out.startswith("STAR")
        assert out.endswith("END")

    def test_marker_appears(self):
        assert "cut" in middle_out("x" * 500, 60)

    def test_tiny_budget_falls_back_to_plain_truncation(self):
        out = middle_out("abcdefghijklmnop", 6)
        assert out == "abcdef", "a marker with 2 chars either side helps nobody"

    def test_stack_trace_keeps_the_cause(self):
        trace = "Traceback:\n" + "  at frame\n" * 400 + "caused by: DNS timeout"
        out = middle_out(trace, 200)
        assert "Traceback" in out
        assert "DNS timeout" in out, "the tail is where the answer is"


class TestTruncateToolResults:
    def make(self):
        return [
            {"role": "user", "content": "x" * 10_000},
            {"role": "assistant", "content": "y" * 10_000},
            {"role": "tool", "tool_call_id": "c1", "name": "read", "content": "z" * 10_000},
        ]

    def test_only_tool_messages_are_cut(self):
        out = truncate_tool_results(self.make(), max_chars=100)
        assert len(out[0]["content"]) == 10_000
        assert len(out[1]["content"]) == 10_000
        assert len(out[2]["content"]) <= 100

    def test_does_not_mutate_the_input(self):
        msgs = self.make()
        truncate_tool_results(msgs, max_chars=100)
        assert len(msgs[2]["content"]) == 10_000, "the caller may still hold this list"

    def test_returns_a_new_list(self):
        msgs = self.make()
        assert truncate_tool_results(msgs) is not msgs

    def test_preserves_the_other_keys(self):
        out = truncate_tool_results(self.make(), max_chars=50)
        assert out[2]["tool_call_id"] == "c1"
        assert out[2]["name"] == "read"
        assert out[2]["role"] == "tool"

    def test_short_results_untouched(self):
        msgs = [{"role": "tool", "tool_call_id": "c", "name": "t", "content": "ok"}]
        assert truncate_tool_results(msgs, max_chars=100)[0]["content"] == "ok"

    def test_non_string_content_is_left_alone(self):
        msgs = [{"role": "tool", "tool_call_id": "c", "name": "t", "content": None}]
        assert truncate_tool_results(msgs)[0]["content"] is None

    def test_empty_list(self):
        assert truncate_tool_results([]) == []
