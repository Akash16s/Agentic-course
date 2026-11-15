"""An MCP client, and the bridge into your own ToolRegistry.

Promoted from Chapter 16.

The payoff of the whole protocol: `bridge_tools` turns a remote MCP server's tools
into ordinary `agentlib` Tools, so a Chapter 3 agent uses them without knowing MCP
exists.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from typing import Any, Callable, TextIO

from agentlib.mcp.protocol import (
    Request,
    Response,
    encode,
    parse_message,
)
from agentlib.mcp.server import PROTOCOL_VERSION


class MCPError(Exception):
    """The server returned a JSON-RPC error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


class MCPClient:
    """Talks to one MCP server over any line-oriented transport.

    `send_line(text) -> reply_line` is injected, so the same client works over
    stdio, a subprocess, HTTP or an in-memory pipe to a server object. That is
    what makes it testable without spawning anything.
    """

    def __init__(self, send_line: Callable[[str], str | None],
                 *, name: str = "agentlib-client", version: str = "0.1.0") -> None:
        self.send_line = send_line
        self.name = name
        self.version = version
        self._ids = itertools.count(1)
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}

    # ------------------------------------------------------------ plumbing

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request = Request(method=method, params=params or {}, id=next(self._ids))
        raw = self.send_line(encode(request))
        if raw is None:
            raise MCPError(-1, f"no reply to {method}")
        message = parse_message(raw)
        if not isinstance(message, Response):
            raise MCPError(-1, f"expected a response to {method}, got {raw[:120]!r}")
        if message.error:
            raise MCPError(message.error.get("code", -1),
                           message.error.get("message", "unknown error"))
        return message.result

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send and do not wait. The id is omitted, which is what makes it a
        notification — the server must not reply."""
        self.send_line(encode(Request(method=method, params=params or {})))

    # ----------------------------------------------------------- handshake

    def initialize(self) -> dict[str, Any]:
        """The two-step handshake: `initialize` (a request), then
        `notifications/initialized` (a notification).

        Two steps because the client may need to do work between learning the
        server's capabilities and declaring itself ready. Skipping the second step
        leaves strict servers waiting forever.
        """
        result = self._call("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": self.name, "version": self.version},
        })
        self.server_info = result.get("serverInfo", {})
        self.capabilities = result.get("capabilities", {}) or {}
        self._notify("notifications/initialized")
        return result

    # ------------------------------------------------------------- methods

    def list_tools(self) -> list[dict[str, Any]]:
        return self._call("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call a tool and return its text. Errors come back as TEXT, not raised —
        the same rule as Chapter 2, so the model can read and recover."""
        result = self._call("tools/call", {"name": name,
                                           "arguments": arguments or {}})
        parts = [
            block.get("text", "")
            for block in result.get("content", [])
            if block.get("type") == "text"
        ]
        return "\n".join(parts)

    def list_resources(self) -> list[dict[str, Any]]:
        return self._call("resources/list").get("resources", [])

    def read_resource(self, uri: str) -> str:
        contents = self._call("resources/read", {"uri": uri}).get("contents", [])
        return "\n".join(c.get("text", "") for c in contents)

    def list_prompts(self) -> list[dict[str, Any]]:
        return self._call("prompts/list").get("prompts", [])

    def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        result = self._call("prompts/get", {"name": name,
                                            "arguments": arguments or {}})
        parts = []
        for message in result.get("messages", []):
            content = message.get("content", {})
            parts.append(content.get("text", "") if isinstance(content, dict)
                         else str(content))
        return "\n".join(parts)


# ------------------------------------------------------------------ bridge


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


# -------------------------------------------------------------- transports


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


def subprocess_transport(command: list[str]) -> Callable[[str], str | None]:
    """Spawn an MCP server as a child process and talk to it over stdio.

    Note `stderr=sys.stderr`: the server's logs must go somewhere visible, and
    they must NOT go to stdout, where they would corrupt the JSON-RPC stream.
    That is the most common failure when running someone else's MCP server.
    """
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=sys.stderr, text=True, bufsize=1,
    )

    def send_line(text: str) -> str | None:
        assert process.stdin and process.stdout
        process.stdin.write(text)
        process.stdin.flush()
        if '"id"' not in text:      # a notification: no reply is coming
            return None
        return process.stdout.readline()

    send_line.process = process  # type: ignore[attr-defined]
    return send_line
