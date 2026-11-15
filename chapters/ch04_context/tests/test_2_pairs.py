"""Tests for Chapter 4, Exercise 2 — message grouping."""

from chapters.ch04_context.exercises.exercise_2_pairs import message_pairs


def assistant_with_calls(*ids):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": i, "type": "function", "function": {"name": "t", "arguments": "{}"}}
            for i in ids
        ],
    }


def tool_msg(call_id):
    return {"role": "tool", "tool_call_id": call_id, "name": "t", "content": "r"}


USER = {"role": "user", "content": "hi"}
PLAIN = {"role": "assistant", "content": "hello"}
SYSTEM = {"role": "system", "content": "sys"}


def roles(groups):
    return [[m["role"] for m in g] for g in groups]


class TestGrouping:
    def test_empty(self):
        assert message_pairs([]) == []

    def test_plain_messages_are_singletons(self):
        assert roles(message_pairs([USER, PLAIN, USER])) == [
            ["user"], ["assistant"], ["user"]
        ]

    def test_system_is_its_own_group(self):
        assert roles(message_pairs([SYSTEM, USER])) == [["system"], ["user"]]

    def test_tool_calls_bind_their_results(self):
        msgs = [USER, assistant_with_calls("c1"), tool_msg("c1"), PLAIN]
        assert roles(message_pairs(msgs)) == [
            ["user"], ["assistant", "tool"], ["assistant"]
        ]

    def test_parallel_tool_calls_stay_in_one_group(self):
        msgs = [assistant_with_calls("c1", "c2"), tool_msg("c1"), tool_msg("c2")]
        assert roles(message_pairs(msgs)) == [["assistant", "tool", "tool"]]

    def test_assistant_without_tool_calls_does_not_absorb(self):
        msgs = [PLAIN, USER]
        assert roles(message_pairs(msgs)) == [["assistant"], ["user"]]

    def test_orphan_tool_message(self):
        # already broken input; keep it as its own group rather than crashing
        assert roles(message_pairs([tool_msg("c1"), USER])) == [["tool"], ["user"]]

    def test_two_tool_rounds(self):
        msgs = [
            USER,
            assistant_with_calls("c1"), tool_msg("c1"),
            assistant_with_calls("c2"), tool_msg("c2"),
            PLAIN,
        ]
        assert roles(message_pairs(msgs)) == [
            ["user"], ["assistant", "tool"], ["assistant", "tool"], ["assistant"]
        ]

    def test_trailing_tool_calls_with_no_results_yet(self):
        msgs = [USER, assistant_with_calls("c1")]
        assert roles(message_pairs(msgs)) == [["user"], ["assistant"]]


class TestInvariant:
    def test_flattening_reproduces_the_input_exactly(self):
        msgs = [
            SYSTEM, USER,
            assistant_with_calls("c1", "c2"), tool_msg("c1"), tool_msg("c2"),
            PLAIN, USER, assistant_with_calls("c3"), tool_msg("c3"),
        ]
        flat = [m for g in message_pairs(msgs) for m in g]
        assert flat == msgs

    def test_no_empty_groups(self):
        msgs = [USER, assistant_with_calls("c1"), tool_msg("c1"), PLAIN]
        assert all(g for g in message_pairs(msgs))
