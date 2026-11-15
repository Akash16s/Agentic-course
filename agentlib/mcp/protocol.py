"""JSON-RPC 2.0 — the wire format MCP is built on.

Promoted from Chapter 16.

MCP is not a new protocol. It is JSON-RPC 2.0, which is thirty lines of framing,
plus an agreed set of method names. Understanding that removes most of the mystery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator

JSONRPC_VERSION = "2.0"

# Standard JSON-RPC error codes, plus the MCP-specific range.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class Request:
    """A call. `id` is None for a NOTIFICATION — fire and forget, no reply.

    The notification/request distinction is the one piece of JSON-RPC people get
    wrong: replying to a notification, or failing to reply to a request, both hang
    the other end.
    """

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str | int | None = None

    @property
    def is_notification(self) -> bool:
        return self.id is None

    def to_dict(self) -> dict[str, Any]:
        message: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": self.method}
        if self.params:
            message["params"] = self.params
        if self.id is not None:
            message["id"] = self.id
        return message


@dataclass
class Response:
    """A reply. Exactly one of `result` or `error`, never both, never neither."""

    id: str | int | None
    result: Any = None
    error: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        message: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": self.id}
        if self.error is not None:
            message["error"] = self.error
        else:
            message["result"] = self.result
        return message


def error_response(id: Any, code: int, message: str,
                   data: Any = None) -> Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return Response(id=id, error=error)


def parse_message(raw: str) -> Request | Response | None:
    """Parse one JSON-RPC message. None if it is not valid.

    A response has `result` or `error`; a request has `method`. Distinguishing on
    those keys rather than on direction is what lets one function handle both ends
    of the connection.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    if "method" in data:
        params = data.get("params")
        return Request(
            method=str(data["method"]),
            params=params if isinstance(params, dict) else {},
            id=data.get("id"),
        )
    if "result" in data or "error" in data:
        return Response(id=data.get("id"), result=data.get("result"),
                        error=data.get("error"))
    return None


# ----------------------------------------------------------------- framing


def encode(message: Request | Response) -> str:
    """One message, one line, newline-terminated.

    Newline-delimited JSON over stdio is the transport MCP uses for local servers.
    It works because JSON never contains a raw newline — `json.dumps` escapes them
    — so a newline unambiguously ends a message.

    `ensure_ascii=False` keeps non-Latin text readable in logs; it stays valid
    JSON either way.
    """
    return json.dumps(message.to_dict(), ensure_ascii=False) + "\n"


def read_messages(stream: Iterator[str]) -> Iterator[Request | Response]:
    """Parse a newline-delimited stream, skipping blank and unparseable lines.

    Skipping rather than raising: a server that dies on one malformed line is a
    server one stray log write can kill. Log it and carry on.
    """
    for line in stream:
        line = line.strip()
        if not line:
            continue
        message = parse_message(line)
        if message is not None:
            yield message
