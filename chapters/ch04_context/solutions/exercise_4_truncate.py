"""SOLUTION — Chapter 4, Exercise 4."""

from __future__ import annotations

from agentlib.llm import Message


#: Shorter than it looks tempting to make it — every character here is a character of
#: real content you are throwing away.
MIDDLE_MARKER = "\n...[{n} chars cut]...\n"


def middle_out(text: str, max_chars: int, marker: str = MIDDLE_MARKER) -> str:
    """Keep the start and the end, cut the middle.

    For tool output — a stack trace, a long file, a big JSON blob — the beginning and
    the end carry most of the signal and the middle is filler. Plain truncation throws
    away the end, which is usually exactly where the error message is.

    If `max_chars` is so small that the marker would dominate, falls back to plain
    truncation: a marker with two characters of content either side helps nobody.
    """
    if len(text) <= max_chars:
        return text

    note = marker.format(n=len(text) - max_chars)
    keep = max_chars - len(note)
    if keep < 8:
        return text[:max_chars]

    head = keep // 2
    tail = keep - head
    return text[:head] + marker.format(n=len(text) - keep) + text[-tail:]


def truncate_tool_results(messages: list[Message], max_chars: int = 4_000) -> list[Message]:
    """Cap every tool result. One unbounded tool return can eat a whole window."""
    out: list[Message] = []
    for message in messages:
        if message.get("role") == "tool" and isinstance(message.get("content"), str):
            message = {**message, "content": middle_out(message["content"], max_chars)}
        out.append(message)
    return out
