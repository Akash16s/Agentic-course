"""Tests for Chapter 2, Exercise 5 — tool-call plumbing."""

import pytest

from agentlib.llm import LLMResponse
from agentlib.testing import tool_call, tool_response
from chapters.ch02_tools.exercises.exercise_3_build_tool import (
    ToolResult,
    build_tool,
)
from chapters.ch02_tools.exercises.exercise_4_registry import ToolRegistry
from chapters.ch02_tools.exercises.exercise_5_execute import (
    ToolCall,
    execute_tool_calls,
    parse_tool_calls,
    tool_result_message,
)


def _add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


# Exercise 5 builds on Exercise 3. Say so rather than exploding during collection.
try:
    add = build_tool(_add, name="add")
except NotImplementedError:  # pragma: no cover
    pytest.skip("finish exercise 3 first", allow_module_level=True)


class TestParseToolCalls:
    def test_no_tool_calls(self):
        assert parse_tool_calls(LLMResponse(text="just talking")) == []

    def test_object_without_the_attribute(self):
        class Bare:
            pass

        assert parse_tool_calls(Bare()) == []

    def test_one_call(self):
        r = tool_response(tool_call("add", {"a": 1, "b": 2}, call_id="c1"))
        calls = parse_tool_calls(r)
        assert len(calls) == 1
        assert calls[0].id == "c1"
        assert calls[0].name == "add"
        assert calls[0].arguments == '{"a": 1, "b": 2}'

    def test_several_calls_keep_order(self):
        r = tool_response(
            tool_call("add", {"a": 1}, call_id="c1"),
            tool_call("add", {"a": 2}, call_id="c2"),
        )
        assert [c.id for c in parse_tool_calls(r)] == ["c1", "c2"]

    def test_sdk_style_objects(self):
        class Fn:
            name = "add"
            arguments = '{"a": 1}'

        class Call:
            id = "c9"
            function = Fn()

        class Resp:
            tool_calls = [Call()]

        calls = parse_tool_calls(Resp())
        assert calls[0].id == "c9" and calls[0].name == "add"

    def test_already_a_toolcall_passes_through(self):
        existing = ToolCall(id="x", name="add", arguments={"a": 1})

        class Resp:
            tool_calls = [existing]

        assert parse_tool_calls(Resp())[0] is existing

    def test_missing_id_becomes_empty_string(self):
        class Resp:
            tool_calls = [{"function": {"name": "add", "arguments": "{}"}}]

        assert parse_tool_calls(Resp())[0].id == ""


class TestToolResultMessage:
    def test_all_four_keys(self):
        call = ToolCall(id="c1", name="add")
        msg = tool_result_message(call, ToolResult("5"))
        assert msg == {
            "role": "tool",
            "tool_call_id": "c1",
            "name": "add",
            "content": "5",
        }

    def test_errors_still_come_back_as_content(self):
        msg = tool_result_message(ToolCall(id="c", name="x"), ToolResult("boom", True))
        assert msg["content"] == "boom"
        assert msg["role"] == "tool"


class TestExecuteToolCalls:
    def test_one_message_per_call(self):
        registry = ToolRegistry([add])
        calls = [
            ToolCall(id="c1", name="add", arguments={"a": 1, "b": 1}),
            ToolCall(id="c2", name="add", arguments={"a": 2, "b": 2}),
        ]
        msgs = execute_tool_calls(registry, calls)
        assert len(msgs) == 2
        assert [m["tool_call_id"] for m in msgs] == ["c1", "c2"]
        assert [m["content"] for m in msgs] == ["2", "4"]

    def test_failures_still_produce_a_message(self):
        registry = ToolRegistry([add])
        calls = [
            ToolCall(id="ok", name="add", arguments={"a": 1, "b": 1}),
            ToolCall(id="bad", name="nonexistent", arguments={}),
        ]
        msgs = execute_tool_calls(registry, calls)
        assert len(msgs) == 2, "a missing result breaks the conversation"
        assert "unknown tool" in msgs[1]["content"]

    def test_empty_list(self):
        assert execute_tool_calls(ToolRegistry([add]), []) == []

    def test_full_round_trip(self):
        from agentlib.conversation import Conversation
        from agentlib.testing import FakeLLMClient

        registry = ToolRegistry([add])
        client = FakeLLMClient(
            [tool_response(tool_call("add", {"a": 2, "b": 3}, call_id="c1")), "It is 5."]
        )
        conv = Conversation("you can add")
        conv.add_user("what is 2+3?")

        first = client.chat(conv.messages, tools=registry.specs())
        conv.add_response(first)
        conv.extend(execute_tool_calls(registry, parse_tool_calls(first)))
        second = client.chat(conv.messages, tools=registry.specs())
        conv.add_response(second)

        roles = [m["role"] for m in conv.messages]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]
        assert conv.messages[2]["tool_calls"], "assistant msg must carry the tool_calls"
        assert conv.last_assistant() == "It is 5."
