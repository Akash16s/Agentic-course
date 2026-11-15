"""Tests for Chapter 4, Exercise 3 — group-aware trimming."""

from agentlib.tokens import estimate_messages_tokens
from chapters.ch04_context.exercises.exercise_3_trim import trim_messages


def user(text="x" * 200):
    return {"role": "user", "content": text}


def assistant(text="y" * 200):
    return {"role": "assistant", "content": text}


def calls(cid="c1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": cid, "type": "function", "function": {"name": "t", "arguments": "{}"}}
        ],
    }


def tool(cid="c1", text="z" * 200):
    return {"role": "tool", "tool_call_id": cid, "name": "t", "content": text}


class TestTrimming:
    def test_empty(self):
        assert trim_messages([], 100) == []

    def test_under_budget_is_untouched(self):
        msgs = [user("hi"), assistant("hello")]
        assert trim_messages(msgs, 10_000) == msgs

    def test_drops_oldest_first(self):
        msgs = [user(f"message {i} " + "x" * 200) for i in range(8)]
        out = trim_messages(msgs, 200, keep_last=1)
        assert len(out) < len(msgs)
        assert "message 0" not in out[0]["content"]
        assert "message 7" in out[-1]["content"]

    def test_keep_last_protects_recent_groups(self):
        msgs = [user() for _ in range(10)]
        out = trim_messages(msgs, 1, keep_last=3)
        assert len(out) == 3, "protected groups survive even when over budget"

    def test_keep_first_protects_the_task_statement(self):
        msgs = [user("THE TASK IS TO MIGRATE THE DB")] + [user() for _ in range(10)]
        out = trim_messages(msgs, 60, keep_first=1, keep_last=1)
        assert "THE TASK" in out[0]["content"]

    def test_result_can_exceed_budget_when_everything_is_protected(self):
        msgs = [user("x" * 4000), user("y" * 4000)]
        out = trim_messages(msgs, 5, keep_first=1, keep_last=1)
        assert len(out) == 2
        assert estimate_messages_tokens(out) > 5


class TestNeverSplitsGroups:
    def test_tool_group_is_kept_whole(self):
        msgs = [user() for _ in range(6)] + [calls(), tool(), assistant("final")]
        out = trim_messages(msgs, 150, keep_last=2)
        # if a tool message survived, its assistant tool_calls must be right before it
        for i, m in enumerate(out):
            if m["role"] == "tool":
                assert i > 0 and out[i - 1].get("tool_calls"), (
                    "orphaned tool message: this is the 400 the chapter warns about"
                )

    def test_never_leaves_tool_calls_without_results(self):
        msgs = [calls("c1"), tool("c1"), user(), calls("c2"), tool("c2")]
        out = trim_messages(msgs, 60, keep_last=1)
        ids_requested = {
            c["id"] for m in out for c in (m.get("tool_calls") or [])
        }
        ids_answered = {m["tool_call_id"] for m in out if m["role"] == "tool"}
        assert ids_requested == ids_answered

    def test_group_boundaries_survive_aggressive_trimming(self):
        msgs = []
        for i in range(6):
            msgs += [user(), calls(f"c{i}"), tool(f"c{i}")]
        out = trim_messages(msgs, 100, keep_last=2)
        for i, m in enumerate(out):
            if m["role"] == "tool":
                assert out[i - 1].get("tool_calls")


class TestBudget:
    def test_gets_under_budget_when_it_can(self):
        msgs = [user() for _ in range(20)]
        out = trim_messages(msgs, 300, keep_last=1)
        assert estimate_messages_tokens(out) <= 300

    def test_head_and_tail_do_not_overlap(self):
        # 2 groups, keep_first=1 + keep_last=6 -> group 0 must not appear twice
        msgs = [user("first"), user("second")]
        out = trim_messages(msgs, 10_000, keep_first=1, keep_last=6)
        assert out == msgs
        assert len(out) == 2, "protected ranges overlapped and duplicated a message"

    def test_keep_counts_larger_than_the_conversation(self):
        msgs = [user("only")]
        assert trim_messages(msgs, 10_000, keep_first=5, keep_last=5) == msgs

    def test_keep_last_zero(self):
        msgs = [user() for _ in range(5)]
        out = trim_messages(msgs, 1, keep_last=0)
        assert out == []
