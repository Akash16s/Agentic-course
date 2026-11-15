"""SOLUTION — Chapter 16, Exercise 2."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

from .exercise_1_protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    Request,
    Response,
    encode,
    error_response,
    read_messages,
)

PROTOCOL_VERSION = "2025-06-18"


@dataclass
class Resource:
    """Read-only context a client can fetch: a file, a record, a config."""

    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    read: Callable[[], str] = field(default_factory=lambda: (lambda: ""))


@dataclass
class Prompt:
    """A reusable prompt template the server offers."""

    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = field(default_factory=list)
    render: Callable[[dict[str, Any]], str] = field(
        default_factory=lambda: (lambda args: "")
    )


class MCPServer:
    """Serves tools, resources and prompts over JSON-RPC.

    >>> server = MCPServer("my-tools")
    >>> server.add_tool(my_tool)
    >>> server.serve_stdio()
    """

    def __init__(self, name: str, *, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self.tools: dict[str, Any] = {}          # name -> agentlib Tool
        self.resources: dict[str, Resource] = {}
        self.prompts: dict[str, Prompt] = {}
        self.initialised = False

    # ---------------------------------------------------------- registration

    def add_tool(self, tool: Any) -> None:
        from agentlib.tools import Tool, build_tool

        if not isinstance(tool, Tool):
            tool = build_tool(tool)
        self.tools[tool.name] = tool

    def add_resource(self, resource: Resource) -> None:
        self.resources[resource.uri] = resource

    def add_prompt(self, prompt: Prompt) -> None:
        self.prompts[prompt.name] = prompt

    # -------------------------------------------------------------- dispatch

    def handle(self, request: Request) -> Response | None:
        """Handle one request. Returns None for notifications.

        A notification gets NO reply, ever. Sending one back is a protocol
        violation that confuses strict clients, and it is the single most common
        bug when people implement JSON-RPC by hand.
        """
        handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "initialize": self._initialize,
            "ping": lambda params: {},
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "resources/list": self._resources_list,
            "resources/read": self._resources_read,
            "prompts/list": self._prompts_list,
            "prompts/get": self._prompts_get,
        }

        if request.method == "notifications/initialized":
            self.initialised = True
            return None
        if request.is_notification:
            return None

        handler = handlers.get(request.method)
        if handler is None:
            return error_response(request.id, METHOD_NOT_FOUND,
                                  f"unknown method: {request.method}")
        try:
            return Response(id=request.id, result=handler(request.params))
        except KeyError as exc:
            return error_response(request.id, INVALID_PARAMS,
                                  f"missing or unknown parameter: {exc}")
        except Exception as exc:  # noqa: BLE001 - a handler bug must not kill the server
            return error_response(request.id, INTERNAL_ERROR,
                                  f"{type(exc).__name__}: {exc}")

    # -------------------------------------------------------------- handlers

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {} if self.tools else None,
                "resources": {} if self.resources else None,
                "prompts": {} if self.prompts else None,
            },
            "serverInfo": {"name": self.name, "version": self.version},
        }

    def _tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    # MCP calls it inputSchema; the OpenAI API calls the same
                    # object `parameters`. Same JSON Schema, different key.
                    "inputSchema": tool.parameters,
                }
                for tool in self.tools.values()
            ]
        }

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params["name"]
        tool = self.tools.get(name)
        if tool is None:
            raise KeyError(name)
        result = tool.call(params.get("arguments") or {})
        # A TOOL FAILURE IS NOT A PROTOCOL ERROR. It comes back as a normal result
        # with isError set, so the model can read it and recover — exactly the
        # rule from Chapter 2. A JSON-RPC error would mean "your request was
        # malformed", which is a different thing.
        return {
            "content": [{"type": "text", "text": result.content}],
            "isError": result.is_error,
        }

    def _resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "resources": [
                {"uri": r.uri, "name": r.name, "description": r.description,
                 "mimeType": r.mime_type}
                for r in self.resources.values()
            ]
        }

    def _resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params["uri"]
        resource = self.resources.get(uri)
        if resource is None:
            raise KeyError(uri)
        return {"contents": [{"uri": uri, "mimeType": resource.mime_type,
                              "text": resource.read()}]}

    def _prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompts": [
                {"name": p.name, "description": p.description,
                 "arguments": p.arguments}
                for p in self.prompts.values()
            ]
        }

    def _prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params["name"]
        prompt = self.prompts.get(name)
        if prompt is None:
            raise KeyError(name)
        text = prompt.render(params.get("arguments") or {})
        return {
            "description": prompt.description,
            "messages": [{"role": "user",
                          "content": {"type": "text", "text": text}}],
        }

    # ------------------------------------------------------------- transport

    def serve_stdio(self, *, stdin: TextIO | None = None,
                    stdout: TextIO | None = None) -> None:
        """Read newline-delimited JSON on stdin, write replies on stdout.

        THE ONE RULE OF STDIO SERVERS: never print anything to stdout that is not
        a JSON-RPC message. One stray `print()` corrupts the stream and the client
        disconnects with a parse error that points nowhere near the real cause.
        Log to STDERR.
        """
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for message in read_messages(stdin):
            if not isinstance(message, Request):
                continue
            response = self.handle(message)
            if response is not None:
                stdout.write(encode(response))
                stdout.flush()
