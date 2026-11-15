"""EXERCISE 3 — An MCP client.

    pytest chapters/ch16_mcp/tests -q -k client
"""

from __future__ import annotations

import itertools
from typing import Any, Callable

from .exercise_1_protocol import Request, Response, encode, parse_message
from .exercise_2_server import PROTOCOL_VERSION


class MCPError(Exception):
    """The server returned a JSON-RPC error. Carries `.code`."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


class MCPClient:
    """Talks to one MCP server over any line-oriented transport.

    __init__(self, send_line: Callable[[str], str | None], *,
             name="agentlib-client", version="0.1.0")

    `send_line(text) -> reply_line or None` is INJECTED. The same client then
    works over stdio, a subprocess, HTTP, or an in-memory pipe to a server object
    — which is why every test in this chapter runs without spawning anything.

    Keep an `itertools.count(1)` for request ids, and `server_info` /
    `capabilities` populated by the handshake.
    """

    def __init__(self, send_line: Callable[[str], str | None],
                 *, name: str = "agentlib-client", version: str = "0.1.0") -> None:
        # TODO: implement
        raise NotImplementedError

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a REQUEST (with an id) and return its `result`.

        Spec:
          * build Request(method, params or {}, id=next(self._ids))
          * send encode(request)
          * no reply           -> raise MCPError(-1, f"no reply to {method}")
          * not a Response     -> raise MCPError(-1, ...)
          * response has error -> raise MCPError(code, message)
          * otherwise          -> return response.result
        """
        # TODO: implement
        raise NotImplementedError

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a NOTIFICATION (no id) and do not wait for anything."""
        # TODO: implement
        raise NotImplementedError

    def initialize(self) -> dict[str, Any]:
        """The two-step handshake.

        Spec:
          1. _call("initialize", {"protocolVersion": PROTOCOL_VERSION,
                                  "capabilities": {},
                                  "clientInfo": {"name": ..., "version": ...}})
          2. store result["serverInfo"] and result["capabilities"]
          3. _notify("notifications/initialized")
          4. return the result

        Two steps because the client may need to do work between learning what
        the server offers and declaring itself ready. Skip step 3 and a strict
        server waits forever, which looks like a hang with no error anywhere.
        """
        # TODO: implement
        raise NotImplementedError

    def list_tools(self) -> list[dict[str, Any]]:
        """`tools/list` -> result["tools"], defaulting to []."""
        # TODO: implement
        raise NotImplementedError

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """`tools/call` -> join the text of every `{"type": "text"}` content block.

        A TOOL ERROR COMES BACK AS TEXT, not as an exception — `isError` is part
        of a successful result. The model reads it and recovers, exactly as in
        Chapter 2. Only a malformed REQUEST raises.
        """
        # TODO: implement
        raise NotImplementedError

    def list_resources(self) -> list[dict[str, Any]]:
        # TODO: implement
        raise NotImplementedError

    def read_resource(self, uri: str) -> str:
        """`resources/read` -> join the "text" of each entry in result["contents"]."""
        # TODO: implement
        raise NotImplementedError

    def list_prompts(self) -> list[dict[str, Any]]:
        # TODO: implement
        raise NotImplementedError

    def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """`prompts/get` -> join the text of each message's content."""
        # TODO: implement
        raise NotImplementedError
