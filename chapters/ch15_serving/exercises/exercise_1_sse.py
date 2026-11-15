"""EXERCISE 1 — Server-Sent Events framing.

    pytest chapters/ch15_serving/tests -q -k sse
"""

from __future__ import annotations

import json
from typing import Any


def sse(data: Any, *, event: str | None = None, id: str | None = None) -> str:
    """Format ONE Server-Sent Event frame.

    Spec, in this order:
      * "event: {event}" line, if given
      * "id: {id}" line, if given
      * the payload: a str is used as-is, anything else is json.dumps'd
      * "data: {line}" FOR EVERY LINE of the payload
      * join with "\\n" and end with "\\n\\n"

    TWO THINGS THAT BREAK REAL SERVICES:

    THE TRAILING BLANK LINE. The frame ends with "\\n\\n", and that blank line is
    what flushes it to the client. One "\\n" and the browser sits there holding
    your bytes in a buffer forever, waiting for a frame that never completes. It
    looks exactly like your server hanging.

    A "data: " PREFIX PER LINE. A JSON blob or a message containing newlines
    silently truncates at the first newline otherwise — the client sees the first
    line and drops the rest, with no error anywhere.

    >>> sse("hello")
    'data: hello\\n\\n'
    >>> sse("two\\nlines")
    'data: two\\ndata: lines\\n\\n'
    """
    # TODO: implement
    raise NotImplementedError


def sse_done() -> str:
    """The conventional terminator: `sse("[DONE]", event="done")`.

    Browsers AUTO-RECONNECT when an SSE stream simply closes. Without an explicit
    sentinel the client reconnects and you run the whole agent again — twice the
    cost, and the user sees the answer start over.
    """
    # TODO: implement
    raise NotImplementedError


def sse_error(message: str) -> str:
    """An error, mid-stream: `sse({"error": message}, event="error")`.

    You CANNOT change the HTTP status after the first byte has gone. A failure at
    second 30 of a 60-second stream cannot become a 500 — the 200 already shipped.
    So the error has to travel inside the stream, and the client has to handle this
    event. If it does not, a mid-stream failure is indistinguishable from a short
    answer, which is the bug behind every "it just stopped" report.
    """
    # TODO: implement
    raise NotImplementedError
