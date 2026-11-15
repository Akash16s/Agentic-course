"""Tests for Chapter 16, Exercise 3 — the client."""

import pytest

from agentlib.tools import tool
from chapters.ch16_mcp.exercises.exercise_1_protocol import (
    Response,
    encode,
    parse_message,
)
from chapters.ch16_mcp.exercises.exercise_2_server import (
    MCPServer,
    Prompt,
    Resource,
)
from chapters.ch16_mcp.exercises.exercise_3_client import MCPClient, MCPError


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def boom() -> str:
    """Always fails."""
    raise RuntimeError("tool exploded")


def make_server():
    server = MCPServer("test-server")
    server.add_tool(add)
    server.add_tool(boom)
    server.add_resource(Resource(uri="file:///notes", name="notes",
                                 read=lambda: "note text"))
    server.add_prompt(Prompt(name="greet", render=lambda a: f"hi {a.get('who')}"))
    return server


class RecordingTransport:
    """Pipes to a server and records every line sent."""

    def __init__(self, server):
        self.server = server
        self.sent: list[str] = []

    def __call__(self, text):
        self.sent.append(text)
        message = parse_message(text.strip())
        response = self.server.handle(message)
        return encode(response) if response is not None else None


@pytest.fixture
def client():
    return MCPClient(RecordingTransport(make_server()))


class TestHandshake:
    def test_initialize(self, client):
        result = client.initialize()
        assert result["serverInfo"]["name"] == "test-server"
        assert client.server_info["name"] == "test-server"

    def test_sends_both_steps(self):
        transport = RecordingTransport(make_server())
        MCPClient(transport).initialize()
        assert len(transport.sent) == 2
        assert "initialize" in transport.sent[0]
        assert "notifications/initialized" in transport.sent[1]

    def test_the_second_step_is_a_notification(self):
        # a request here would make a strict server reply, and nobody is listening
        transport = RecordingTransport(make_server())
        MCPClient(transport).initialize()
        assert '"id"' not in transport.sent[1]

    def test_sends_client_info(self):
        transport = RecordingTransport(make_server())
        MCPClient(transport, name="my-client", version="9.9").initialize()
        assert "my-client" in transport.sent[0]

    def test_records_capabilities(self, client):
        client.initialize()
        assert isinstance(client.capabilities, dict)


class TestIds:
    def test_ids_increment(self):
        transport = RecordingTransport(make_server())
        client = MCPClient(transport)
        client.list_tools()
        client.list_tools()
        ids = [parse_message(line.strip()).id for line in transport.sent]
        assert ids == [1, 2]

    def test_requests_carry_an_id(self):
        transport = RecordingTransport(make_server())
        MCPClient(transport).list_tools()
        assert '"id"' in transport.sent[0]


class TestTools:
    def test_list(self, client):
        assert {t["name"] for t in client.list_tools()} == {"add", "boom"}

    def test_call(self, client):
        assert client.call_tool("add", {"a": 2, "b": 3}) == "5"

    def test_call_with_no_arguments(self, client):
        assert isinstance(client.call_tool("boom"), str)

    def test_a_tool_error_comes_back_as_text(self, client):
        # isError is part of a SUCCESSFUL result; the model reads and recovers
        text = client.call_tool("boom")
        assert "RuntimeError" in text

    def test_a_malformed_request_raises(self, client):
        with pytest.raises(MCPError):
            client.call_tool("no_such_tool", {})

    def test_error_carries_the_code(self, client):
        with pytest.raises(MCPError) as exc:
            client.call_tool("no_such_tool", {})
        assert exc.value.code == -32602


class TestResourcesAndPrompts:
    def test_list_resources(self, client):
        assert client.list_resources()[0]["uri"] == "file:///notes"

    def test_read_resource(self, client):
        assert client.read_resource("file:///notes") == "note text"

    def test_list_prompts(self, client):
        assert client.list_prompts()[0]["name"] == "greet"

    def test_get_prompt(self, client):
        assert "Akash" in client.get_prompt("greet", {"who": "Akash"})


class TestTransportFailures:
    def test_no_reply_raises(self):
        client = MCPClient(lambda text: None)
        with pytest.raises(MCPError, match="no reply"):
            client.list_tools()

    def test_garbage_reply_raises(self):
        client = MCPClient(lambda text: "not json at all")
        with pytest.raises(MCPError):
            client.list_tools()

    def test_a_request_shaped_reply_raises(self):
        client = MCPClient(lambda text: '{"jsonrpc":"2.0","method":"surprise"}')
        with pytest.raises(MCPError):
            client.list_tools()
