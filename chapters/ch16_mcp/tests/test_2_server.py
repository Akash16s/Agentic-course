"""Tests for Chapter 16, Exercise 2 — the server."""

import io
import json

import pytest

from agentlib.tools import tool
from chapters.ch16_mcp.exercises.exercise_1_protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    Request,
    encode,
    parse_message,
)
from chapters.ch16_mcp.exercises.exercise_2_server import (
    MCPServer,
    Prompt,
    Resource,
)


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def boom() -> str:
    """Always fails."""
    raise RuntimeError("tool exploded")


@pytest.fixture
def server():
    s = MCPServer("test-server", version="1.2.3")
    s.add_tool(add)
    s.add_tool(boom)
    s.add_resource(Resource(uri="file:///notes", name="notes",
                            description="my notes", read=lambda: "note text"))
    s.add_prompt(Prompt(name="greet", description="Greet someone",
                        arguments=[{"name": "who", "required": True}],
                        render=lambda a: f"Say hello to {a.get('who', 'nobody')}"))
    return s


class TestHandshake:
    def test_initialize(self, server):
        result = server.handle(Request("initialize", id=1)).result
        assert result["serverInfo"] == {"name": "test-server", "version": "1.2.3"}
        assert "protocolVersion" in result
        assert "capabilities" in result

    def test_initialized_notification_gets_no_reply(self, server):
        # replying to a notification is a protocol violation
        assert server.handle(Request("notifications/initialized")) is None
        assert server.initialised

    def test_any_notification_gets_no_reply(self, server):
        assert server.handle(Request("tools/list")) is None

    def test_ping(self, server):
        assert server.handle(Request("ping", id=1)).ok


class TestTools:
    def test_list(self, server):
        tools = server.handle(Request("tools/list", id=1)).result["tools"]
        assert {t["name"] for t in tools} == {"add", "boom"}

    def test_list_uses_inputschema_not_parameters(self, server):
        # MCP says inputSchema; the OpenAI API says parameters. Same object.
        tools = server.handle(Request("tools/list", id=1)).result["tools"]
        entry = next(t for t in tools if t["name"] == "add")
        assert "inputSchema" in entry
        assert entry["inputSchema"]["properties"]["a"]["type"] == "integer"

    def test_call(self, server):
        response = server.handle(Request(
            "tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}}, id=1))
        assert response.result["content"][0]["text"] == "5"
        assert response.result["isError"] is False

    def test_call_with_no_arguments(self, server):
        @tool
        def now() -> str:
            """Current time."""
            return "12:00"

        server.add_tool(now)
        response = server.handle(Request("tools/call", {"name": "now"}, id=1))
        assert response.result["content"][0]["text"] == "12:00"

    def test_a_failing_tool_is_a_successful_call(self, server):
        # a JSON-RPC error would mean "your request was malformed", which the
        # model cannot act on
        response = server.handle(Request("tools/call", {"name": "boom"}, id=1))
        assert response.ok, "a tool failure is not a protocol error"
        assert response.result["isError"] is True
        assert "RuntimeError" in response.result["content"][0]["text"]

    def test_unknown_tool_is_invalid_params(self, server):
        response = server.handle(Request("tools/call", {"name": "nope"}, id=1))
        assert not response.ok
        assert response.error["code"] == INVALID_PARAMS

    def test_missing_name_is_invalid_params(self, server):
        response = server.handle(Request("tools/call", {}, id=1))
        assert response.error["code"] == INVALID_PARAMS


class TestResources:
    def test_list(self, server):
        resources = server.handle(Request("resources/list", id=1)).result["resources"]
        assert resources[0]["uri"] == "file:///notes"
        assert resources[0]["name"] == "notes"

    def test_read(self, server):
        result = server.handle(Request(
            "resources/read", {"uri": "file:///notes"}, id=1)).result
        assert result["contents"][0]["text"] == "note text"

    def test_unknown_uri(self, server):
        response = server.handle(Request("resources/read", {"uri": "nope"}, id=1))
        assert response.error["code"] == INVALID_PARAMS


class TestPrompts:
    def test_list(self, server):
        prompts = server.handle(Request("prompts/list", id=1)).result["prompts"]
        assert prompts[0]["name"] == "greet"
        assert prompts[0]["arguments"][0]["name"] == "who"

    def test_get(self, server):
        result = server.handle(Request(
            "prompts/get", {"name": "greet", "arguments": {"who": "Akash"}},
            id=1)).result
        assert "Akash" in result["messages"][0]["content"]["text"]

    def test_unknown_prompt(self, server):
        response = server.handle(Request("prompts/get", {"name": "nope"}, id=1))
        assert response.error["code"] == INVALID_PARAMS


class TestErrors:
    def test_unknown_method(self, server):
        response = server.handle(Request("does/not/exist", id=1))
        assert response.error["code"] == METHOD_NOT_FOUND

    def test_a_broken_resource_does_not_kill_the_server(self, server):
        def explode():
            raise RuntimeError("disk on fire")

        server.add_resource(Resource(uri="bad://x", name="bad", read=explode))
        response = server.handle(Request("resources/read", {"uri": "bad://x"}, id=1))
        assert response.error["code"] == INTERNAL_ERROR
        assert server.handle(Request("ping", id=2)).ok, "the server survived"


class TestStdio:
    def test_round_trip(self, server):
        stdin = io.StringIO(encode(Request("tools/list", id=1)))
        stdout = io.StringIO()
        server.serve_stdio(stdin=stdin, stdout=stdout)
        response = parse_message(stdout.getvalue().strip())
        assert response.ok

    def test_notifications_produce_no_output(self, server):
        stdin = io.StringIO(encode(Request("notifications/initialized")))
        stdout = io.StringIO()
        server.serve_stdio(stdin=stdin, stdout=stdout)
        assert stdout.getvalue() == ""

    def test_garbage_lines_are_skipped(self, server):
        stdin = io.StringIO(
            "log line that should have gone to stderr\n"
            + encode(Request("ping", id=1))
            + "{broken\n"
            + encode(Request("ping", id=2))
        )
        stdout = io.StringIO()
        server.serve_stdio(stdin=stdin, stdout=stdout)
        lines = [l for l in stdout.getvalue().split("\n") if l.strip()]
        assert len(lines) == 2

    def test_one_message_per_line(self, server):
        stdin = io.StringIO(
            encode(Request("ping", id=1)) + encode(Request("ping", id=2))
        )
        stdout = io.StringIO()
        server.serve_stdio(stdin=stdin, stdout=stdout)
        for line in stdout.getvalue().strip().split("\n"):
            json.loads(line)
