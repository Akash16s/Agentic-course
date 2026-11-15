"""EXERCISE 1 — JSON-RPC 2.0.

    pytest chapters/ch16_mcp/tests -q -k protocol
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator

JSONRPC_VERSION = "2.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class Request:
    """method: str, params: dict = {}, id: str|int|None = None

    `id is None` means NOTIFICATION: fire and forget, no reply, ever.
    """

    method: str

    @property
    def is_notification(self) -> bool:
        # TODO: implement
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """{"jsonrpc": "2.0", "method": ...} plus "params" only when non-empty and
        "id" only when not None.

        OMITTING THE ID IS WHAT MAKES IT A NOTIFICATION. `"id": null` is a
        different thing — a request with a null id — and strict servers treat it
        differently.
        """
        # TODO: implement
        raise NotImplementedError


@dataclass
class Response:
    """id: str|int|None, result: Any = None, error: dict|None = None

    EXACTLY ONE of result/error, never both, never neither.
    """

    id: str | int | None

    @property
    def ok(self) -> bool:
        """error is None."""
        # TODO: implement
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """{"jsonrpc": "2.0", "id": ...} plus "error" if there is one, ELSE
        "result". Never both keys."""
        # TODO: implement
        raise NotImplementedError


def error_response(id: Any, code: int, message: str, data: Any = None) -> Response:
    """Response with error={"code","message"} and "data" only when given."""
    # TODO: implement
    raise NotImplementedError


def parse_message(raw: str) -> Request | Response | None:
    """Parse one JSON-RPC message. None if it is not valid. NEVER raises.

    Spec:
      * not valid JSON, or not a dict -> None
      * has "method"                  -> a Request (params must be a dict, else {})
      * has "result" or "error"       -> a Response
      * otherwise                     -> None

    Dispatching on the KEYS rather than on which end you are is what lets one
    function handle both sides of the connection — and MCP is bidirectional, so
    you will need that.
    """
    # TODO: implement
    raise NotImplementedError


def encode(message: Request | Response) -> str:
    """One message, one line: `json.dumps(...) + "\\n"`.

    Use `ensure_ascii=False` so non-Latin text stays readable in logs; it remains
    valid JSON either way.

    Newline-delimited works because json.dumps ESCAPES newlines inside strings, so
    a raw newline can only ever mean "message ends here".
    """
    # TODO: implement
    raise NotImplementedError


def read_messages(stream: Iterator[str]) -> Iterator[Request | Response]:
    """Parse a newline-delimited stream, SKIPPING blank and unparseable lines.

    Skip, do not raise. A server that dies on one malformed line is a server that
    one stray log write can kill — and something will eventually write to that
    stream that should not have.
    """
    # TODO: implement
    raise NotImplementedError
