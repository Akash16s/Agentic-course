"""Tests for Exercise 2 — the Conversation object."""

import pytest

from agentlib.llm import LLMResponse, Usage
from chapters.ch01_agent_loop.exercises.exercise_2_conversation import Conversation


class TestConstruction:
    def test_empty_conversation(self):
        c = Conversation()
        assert len(c) == 0
        assert c.messages == []
        assert c.system is None

    def test_with_system_prompt(self):
        c = Conversation("You are terse.")
        assert c.system == "You are terse."
        assert len(c) == 0, "the system prompt is configuration, not a conversation turn"
        assert c.messages == [{"role": "system", "content": "You are terse."}]

    def test_system_is_always_first(self):
        c = Conversation("sys")
        c.add_user("a").add_assistant("b")
        assert c.messages[0] == {"role": "system", "content": "sys"}

    def test_set_system_replaces_without_losing_history(self):
        c = Conversation("old")
        c.add_user("hello")
        c.set_system("new")
        assert c.system == "new"
        assert c.messages == [
            {"role": "system", "content": "new"},
            {"role": "user", "content": "hello"},
        ]


class TestAdding:
    def test_add_user_and_assistant(self):
        c = Conversation()
        c.add_user("hi")
        c.add_assistant("hello")
        assert c.messages == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]

    def test_methods_chain(self):
        c = Conversation()
        result = c.add_user("a").add_assistant("b").add_user("c")
        assert result is c
        assert len(c) == 3

    def test_cannot_append_a_system_message(self):
        c = Conversation()
        with pytest.raises(ValueError):
            c.add_message("system", "sneaky")

    def test_add_response(self):
        c = Conversation()
        r = LLMResponse(text="from the model", usage=Usage(10, 5), model="m")
        c.add_response(r)
        assert c.messages == [{"role": "assistant", "content": "from the model"}]

    def test_add_message_arbitrary_role(self):
        # 'tool' shows up in Chapter 2 and must already work.
        c = Conversation()
        c.add_message("tool", "42")
        assert c.messages[0]["role"] == "tool"


class TestIsolation:
    def test_messages_returns_a_copy_of_the_list(self):
        c = Conversation("sys")
        c.add_user("hi")
        got = c.messages
        got.append({"role": "user", "content": "injected"})
        assert len(c.messages) == 2, "external mutation leaked into the conversation"

    def test_messages_returns_copies_of_the_dicts(self):
        c = Conversation()
        c.add_user("hi")
        c.messages[0]["content"] = "tampered"
        assert c.messages[0]["content"] == "hi", "the dicts are shared, not copied"

    def test_copy_is_independent(self):
        a = Conversation("sys")
        a.add_user("one")
        b = a.copy()
        b.add_user("two")
        b.set_system("other")
        assert len(a) == 1 and len(b) == 2
        assert a.system == "sys" and b.system == "other"


class TestReading:
    def test_len_excludes_system(self):
        c = Conversation("sys")
        c.add_user("a").add_assistant("b")
        assert len(c) == 2

    def test_last_assistant(self):
        c = Conversation()
        assert c.last_assistant() is None
        c.add_user("q")
        assert c.last_assistant() is None
        c.add_assistant("first")
        c.add_user("q2")
        c.add_assistant("second")
        assert c.last_assistant() == "second"

    def test_token_estimate_grows(self):
        c = Conversation("sys")
        before = c.token_estimate()
        c.add_user("x" * 400)
        assert c.token_estimate() >= before + 100


class TestTrimming:
    def test_trims_oldest_first(self):
        c = Conversation("sys")
        for i in range(10):
            c.add_user(f"message number {i} " + "x" * 100)
        dropped = c.trim_to(80)
        assert dropped > 0
        contents = [m["content"] for m in c.messages if m["role"] != "system"]
        assert not any("number 0" in x for x in contents), "oldest should go first"
        assert any("number 9" in x for x in contents), "newest must survive"

    def test_never_drops_the_system_prompt(self):
        c = Conversation("IMPORTANT SYSTEM RULES " + "y" * 500)
        for i in range(10):
            c.add_user("x" * 200)
        c.trim_to(10)
        assert c.messages[0]["role"] == "system"
        assert c.system.startswith("IMPORTANT SYSTEM RULES")

    def test_keeps_at_least_one_message(self):
        c = Conversation("sys")
        c.add_user("x" * 10_000)
        c.trim_to(5)
        assert len(c) == 1, "an empty conversation is worse than an oversized one"

    def test_returns_number_dropped(self):
        c = Conversation()
        for i in range(5):
            c.add_user("x" * 400)  # ~100 tokens each
        dropped = c.trim_to(250)
        assert dropped == len([1 for _ in range(5)]) - len(c)
        assert dropped >= 2

    def test_noop_when_already_small(self):
        c = Conversation("sys")
        c.add_user("hi")
        assert c.trim_to(10_000) == 0
        assert len(c) == 1
