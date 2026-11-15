"""SOLUTION — Chapter 15, Exercise 1."""

from __future__ import annotations

import json
from typing import Any


def sse(data: Any, *, event: str | None = None, id: str | None = None) -> str:
    """Format one Server-Sent Event frame.

    The format is small and unforgiving:
      * "field: value\\n" lines, then a BLANK LINE to end the frame
      * multi-line data needs a "data: " prefix PER LINE
      * the blank line is what flushes it to the browser; forget it and the client
        hangs forever with the bytes sitting in a buffer

    Non-string data is JSON-encoded, which is what you want for structured events.
    """
    lines: list[str] = []
    if event is not None:
        lines.append(f"event: {event}")
    if id is not None:
        lines.append(f"id: {id}")
    payload = data if isinstance(data, str) else json.dumps(data)
    for line in payload.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


def sse_done() -> str:
    """The conventional terminator. Browsers reconnect on a bare stream close,
    so you send an explicit sentinel and the client stops on it."""
    return sse("[DONE]", event="done")


def sse_error(message: str) -> str:
    """An error mid-stream.

    You cannot change the HTTP status after the first byte, so a failure halfway
    through a stream has to be *in* the stream. Clients must handle this event or
    a mid-stream failure looks like a truncated answer.
    """
    return sse({"error": message}, event="error")
