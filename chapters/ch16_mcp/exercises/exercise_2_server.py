"""EXERCISE 2 — An MCP server.

    pytest chapters/ch16_mcp/tests -q -k server
"""

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
    """Read-only context, addressed by URI. Chosen by the CLIENT, not the model.

    uri, name, description="", mime_type="text/plain", read: Callable[[], str]
    """

    uri: str
    name: str


@dataclass
class Prompt:
    """A reusable template. Chosen by the USER.

    name, description="", arguments: list[dict] = [],
    render: Callable[[dict], str]
    """

    name: str


class MCPServer:
    """Serves tools, resources and prompts over JSON-RPC.

    __init__(self, name: str, *, version: str = "0.1.0")
      self.tools / self.resources / self.prompts as dicts
      self.initialised = False
    """

    def __init__(self, name: str, *, version: str = "0.1.0") -> None:
        # TODO: implement
        raise NotImplementedError

    def add_tool(self, tool: Any) -> None:
        """Accept an agentlib Tool OR a plain function (wrap with build_tool)."""
        # TODO: implement
        raise NotImplementedError

    def add_resource(self, resource: Resource) -> None:
        # TODO: implement
        raise NotImplementedError

    def add_prompt(self, prompt: Prompt) -> None:
        # TODO: implement
        raise NotImplementedError

    def handle(self, request: Request) -> Response | None:
        """Dispatch one request. RETURNS None FOR NOTIFICATIONS.

        Spec:
          * "notifications/initialized" -> set self.initialised, return None
          * any other notification      -> return None
          * unknown method              -> error_response(METHOD_NOT_FOUND)
          * KeyError from a handler     -> error_response(INVALID_PARAMS)
          * any other exception         -> error_response(INTERNAL_ERROR)
          * otherwise                   -> Response(id, result=handler(params))

        Methods: initialize, ping, tools/list, tools/call, resources/list,
                 resources/read, prompts/list, prompts/get

        NEVER REPLY TO A NOTIFICATION. It is a protocol violation, strict clients
        get confused, and it is the most common hand-rolled-JSON-RPC bug there is.

        CATCH Exception around handlers. A bug in one tool must not take down the
        server and every other tool with it.
        """
        # TODO: implement
        raise NotImplementedError

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """{"protocolVersion", "capabilities", "serverInfo": {name, version}}

        `capabilities` advertises which of tools/resources/prompts you actually
        have — a client should not call tools/list on a server with no tools.
        """
        # TODO: implement
        raise NotImplementedError

    def _tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """{"tools": [{"name", "description", "inputSchema"}]}

        NOTE THE KEY: MCP says `inputSchema`; the OpenAI API says `parameters`.
        Same JSON Schema object, different name. Getting this wrong is the single
        most common MCP bug and it presents as "the model ignores my tool".
        """
        # TODO: implement
        raise NotImplementedError

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run a tool.

        Spec:
          * params["name"]; unknown -> raise KeyError(name) (becomes INVALID_PARAMS)
          * result = tool.call(params.get("arguments") or {})
          * return {"content": [{"type": "text", "text": result.content}],
                    "isError": result.is_error}

        A FAILING TOOL IS A SUCCESSFUL CALL that returned a failure. A JSON-RPC
        error means "your request was malformed", which is a different thing and
        one the model cannot act on. Chapter 2's rule, at the protocol level.
        """
        # TODO: implement
        raise NotImplementedError

    def _resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """{"resources": [{"uri","name","description","mimeType"}]}"""
        # TODO: implement
        raise NotImplementedError

    def _resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """{"contents": [{"uri","mimeType","text"}]}; unknown uri -> KeyError."""
        # TODO: implement
        raise NotImplementedError

    def _prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """{"prompts": [{"name","description","arguments"}]}"""
        # TODO: implement
        raise NotImplementedError

    def _prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """{"description", "messages": [{"role":"user",
            "content":{"type":"text","text": rendered}}]}"""
        # TODO: implement
        raise NotImplementedError

    def serve_stdio(self, *, stdin: TextIO | None = None,
                    stdout: TextIO | None = None) -> None:
        """Read newline-delimited JSON from stdin, write replies to stdout.

        THE ONE RULE OF STDIO SERVERS: nothing but JSON-RPC messages goes to
        stdout. One stray print(), or one library that logs to stdout, corrupts
        the stream and the client reports a parse error pointing nowhere near the
        cause. Log to STDERR.

        And FLUSH after every write, or your reply sits in a buffer while the
        client waits.
        """
        # TODO: implement
        raise NotImplementedError
