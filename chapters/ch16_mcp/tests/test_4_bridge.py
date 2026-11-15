"""Tests for Chapter 16, Exercise 4 — the bridge."""

import pytest

from agentlib.agent import Agent
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import Tool, ToolRegistry, tool
from chapters.ch16_mcp.exercises.exercise_2_server import MCPServer
from chapters.ch16_mcp.exercises.exercise_3_client import MCPClient
from chapters.ch16_mcp.exercises.exercise_4_bridge import (
    bridge_tools,
    in_memory_transport,
)


@tool
def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: The first number.
        b: The second number.
    """
    return a + b


@tool
def echo(text: str) -> str:
    """Echo the text back."""
    return text


@tool
def failing() -> str:
    """Always fails."""
    raise RuntimeError("remote boom")


def make_client(*tools):
    server = MCPServer("remote")
    for t in tools:
        server.add_tool(t)
    client = MCPClient(in_memory_transport(server))
    client.initialize()
    return client


class TestInMemoryTransport:
    def test_round_trip(self):
        client = make_client(add)
        assert client.call_tool("add", {"a": 1, "b": 2}) == "3"

    def test_notifications_return_none(self):
        from chapters.ch16_mcp.exercises.exercise_1_protocol import Request, encode

        transport = in_memory_transport(MCPServer("x"))
        assert transport(encode(Request("notifications/initialized"))) is None

    def test_garbage_returns_none(self):
        assert in_memory_transport(MCPServer("x"))("not json\n") is None


class TestBridgeTools:
    def test_returns_agentlib_tools(self):
        tools = bridge_tools(make_client(add, echo))
        assert len(tools) == 2
        assert all(isinstance(t, Tool) for t in tools)

    def test_names_are_preserved(self):
        assert {t.name for t in bridge_tools(make_client(add, echo))} == {"add", "echo"}

    def test_prefix(self):
        tools = bridge_tools(make_client(add, echo), prefix="remote_")
        assert {t.name for t in tools} == {"remote_add", "remote_echo"}

    def test_descriptions_are_carried_over(self):
        tool_obj = bridge_tools(make_client(add))[0]
        assert "Add two numbers" in tool_obj.description

    def test_inputschema_becomes_parameters(self):
        # the entire translation between MCP and the OpenAI tool format
        tool_obj = bridge_tools(make_client(add))[0]
        assert tool_obj.parameters["properties"]["a"]["type"] == "integer"
        assert tool_obj.parameters["required"] == ["a", "b"]

    def test_param_descriptions_survive_the_round_trip(self):
        tool_obj = bridge_tools(make_client(add))[0]
        assert "first number" in tool_obj.parameters["properties"]["a"]["description"].lower()

    def test_calling_a_bridged_tool_works(self):
        tool_obj = bridge_tools(make_client(add))[0]
        assert tool_obj.call({"a": 4, "b": 5}).content == "9"

    def test_each_tool_calls_its_own_remote(self):
        # the late-binding closure bug: every bridged tool calling the last one
        tools = {t.name: t for t in bridge_tools(make_client(add, echo))}
        assert tools["echo"].call({"text": "hello"}).content == "hello"
        assert tools["add"].call({"a": 1, "b": 1}).content == "2"

    def test_a_remote_failure_comes_back_as_content(self):
        tool_obj = bridge_tools(make_client(failing))[0]
        assert "remote boom" in tool_obj.call({}).content

    def test_no_tools(self):
        assert bridge_tools(make_client()) == []


class TestWithTheRegistry:
    def test_registers(self):
        registry = ToolRegistry(bridge_tools(make_client(add, echo)))
        assert set(registry.names) == {"add", "echo"}

    def test_executes(self):
        registry = ToolRegistry(bridge_tools(make_client(add)))
        assert registry.execute("add", {"a": 7, "b": 8}).content == "15"

    def test_json_string_arguments(self):
        registry = ToolRegistry(bridge_tools(make_client(add)))
        assert registry.execute("add", '{"a": 1, "b": 2}').content == "3"

    def test_specs_are_valid_for_the_api(self):
        import json

        registry = ToolRegistry(bridge_tools(make_client(add)))
        spec = registry.specs()[0]
        assert spec["type"] == "function"
        assert set(spec["function"]) == {"name", "description", "parameters"}
        json.dumps(spec)

    def test_two_servers_collide_without_a_prefix(self):
        registry = ToolRegistry(bridge_tools(make_client(add)))
        with pytest.raises(ValueError):
            for t in bridge_tools(make_client(add)):
                registry.register(t)

    def test_prefixes_prevent_the_collision(self):
        registry = ToolRegistry(bridge_tools(make_client(add), prefix="a_"))
        for t in bridge_tools(make_client(add), prefix="b_"):
            registry.register(t)
        assert set(registry.names) == {"a_add", "b_add"}


class TestWithAnAgent:
    def test_the_agent_does_not_know_mcp_exists(self):
        registry = ToolRegistry(bridge_tools(make_client(add), prefix="calc_"))
        fake = FakeLLMClient([
            tool_response(tool_call("calc_add", {"a": 7, "b": 8})),
            "The answer is 15.",
        ])
        result = Agent(fake, tools=registry).run("what is 7+8?")
        assert result.output == "The answer is 15."
        assert result.tool_sequence == ["calc_add"]
        assert result.steps[0].tool_messages[0]["content"] == "15"
