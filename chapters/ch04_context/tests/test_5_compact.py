"""Tests for Chapter 4, Exercise 5 — compaction."""

from chapters.ch04_context.exercises.exercise_5_compact import (
    compact,
    render_transcript,
)


def user(text):
    return {"role": "user", "content": text}


def assistant(text):
    return {"role": "assistant", "content": text}


def calls(name="search"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": name, "arguments": "{}"}}
        ],
    }


def tool(text="result"):
    return {"role": "tool", "tool_call_id": "c1", "name": "search", "content": text}


class TestRenderTranscript:
    def test_basic(self):
        out = render_transcript([user("hello"), assistant("hi")])
        assert out == "USER: hello\nASSISTANT: hi"

    def test_none_content_becomes_empty(self):
        out = render_transcript([{"role": "assistant", "content": None}])
        assert out == "ASSISTANT:"or out == "ASSISTANT: "

    def test_records_tool_calls(self):
        out = render_transcript([calls("search")])
        assert "search" in out, (
            "without this the summary loses the record of what the agent DID"
        )
        assert "called" in out

    def test_records_several_tool_calls(self):
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "1", "function": {"name": "read"}},
                {"id": "2", "function": {"name": "write"}},
            ],
        }
        out = render_transcript([msg])
        assert "read" in out and "write" in out

    def test_tool_results_included(self):
        out = render_transcript([tool("the answer is 42")])
        assert "42" in out
        assert out.startswith("TOOL:")

    def test_empty(self):
        assert render_transcript([]) == ""


class TestCompact:
    def msgs(self, n=10):
        return [user(f"turn {i}") for i in range(n)]

    def test_short_conversations_are_untouched(self):
        called = []
        msgs = self.msgs(3)
        out = compact(msgs, lambda t: called.append(t) or "SUM", keep_recent=4)
        assert out == msgs
        assert called == [], "do not spend an API call to summarise nothing"

    def test_exactly_keep_recent_is_untouched(self):
        msgs = self.msgs(4)
        assert compact(msgs, lambda t: "SUM", keep_recent=4) == msgs

    def test_replaces_old_turns_with_a_summary(self):
        out = compact(self.msgs(10), lambda t: "SUMMARY TEXT", keep_recent=3)
        assert len(out) == 4
        assert "SUMMARY TEXT" in out[0]["content"]

    def test_summary_is_a_user_message(self):
        out = compact(self.msgs(10), lambda t: "S", keep_recent=3)
        assert out[0]["role"] == "user", (
            "mid-conversation system messages are ignored or rejected"
        )

    def test_summary_is_labelled(self):
        out = compact(self.msgs(10), lambda t: "S", keep_recent=3)
        assert "Summary" in out[0]["content"]

    def test_recent_turns_are_verbatim(self):
        msgs = self.msgs(10)
        out = compact(msgs, lambda t: "S", keep_recent=3)
        assert out[1:] == msgs[-3:]

    def test_summariser_sees_only_the_old_turns(self):
        seen = {}
        msgs = self.msgs(10)
        compact(msgs, lambda t: seen.setdefault("t", t) or "S", keep_recent=3)
        assert "turn 0" in seen["t"]
        assert "turn 6" in seen["t"]
        assert "turn 7" not in seen["t"], "never summarise the current state"

    def test_does_not_split_tool_groups(self):
        msgs = [user("go")] + [calls(), tool()] * 5 + [assistant("done")]
        out = compact(msgs, lambda t: "S", keep_recent=2)
        for i, m in enumerate(out):
            if m["role"] == "tool":
                assert i > 0 and out[i - 1].get("tool_calls")

    def test_does_not_mutate_the_input(self):
        msgs = self.msgs(10)
        before = [dict(m) for m in msgs]
        compact(msgs, lambda t: "S", keep_recent=3)
        assert msgs == before

    def test_shrinks_the_message_count(self):
        msgs = self.msgs(30)
        assert len(compact(msgs, lambda t: "S", keep_recent=4)) == 5
