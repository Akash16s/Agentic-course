"""SOLUTION — Chapter 16, Exercise 4."""

from __future__ import annotations

from typing import Any, Callable

from .exercise_1_protocol import Request, encode, parse_message
from .exercise_3_client import MCPClient


def in_memory_transport(server: Any) -> Callable[[str], str | None]:
    """Wire a client straight to a server object. No process, no sockets.

    Ideal for tests and for embedding a server in the same program.
    """
    def send_line(text: str) -> str | None:
        message = parse_message(text.strip())
        if not isinstance(message, Request):
            return None
        response = server.handle(message)
        return encode(response) if response is not None else None
    return send_line

def bridge_tools(client: MCPClient, *, prefix: str = "") -> list[Any]:
    """Turn a remote server's tools into ordinary `agentlib` Tools.

    THIS IS THE POINT OF MCP. After this, a Chapter 3 agent calls a remote tool
    with no idea that a protocol, a subprocess or a network is involved. The
    registry, the loop, the traces and the evals all work unchanged.

    `prefix` namespaces them ("github_create_issue"), which you need the moment
    you connect two servers that both offer a `search`.
    """
    from agentlib.tools import Tool

    tools: list[Tool] = []
    for spec in client.list_tools():
        name = spec["name"]

        def make_caller(remote_name: str) -> Callable[..., str]:
            def call(**arguments: Any) -> str:
                return client.call_tool(remote_name, arguments)
            return call

        tools.append(Tool(
            name=f"{prefix}{name}",
            description=spec.get("description", ""),
            # MCP says inputSchema, the OpenAI API says parameters: same JSON
            # Schema object, different key. This line is the entire translation.
            parameters=spec.get("inputSchema") or {"type": "object", "properties": {}},
            func=make_caller(name),
        ))
    return tools
