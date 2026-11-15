"""EXERCISE 4 — Bounding tool output.

    pytest chapters/ch04_context/tests -q -k truncate
"""

from __future__ import annotations

from agentlib.llm import Message

MIDDLE_MARKER = "\n...[{n} chars cut]...\n"


def middle_out(text: str, max_chars: int, marker: str = MIDDLE_MARKER) -> str:
    """Keep the head and the tail, cut the middle.

    Spec:
      * len(text) <= max_chars                  -> return text unchanged
      * compute note = marker.format(n=len(text) - max_chars)
        keep = max_chars - len(note)
      * keep < 8  -> the marker would dominate; return text[:max_chars]
      * otherwise -> text[:keep//2]
                     + marker.format(n=len(text) - keep)
                     + text[-(keep - keep//2):]

    The result is never longer than max_chars.

    WHY the middle and not the tail: a stack trace starts with boilerplate and ends
    with the cause. A JSON response starts with metadata and ends with the data. Plain
    `text[:n]` reliably keeps the least informative half.

    >>> middle_out("abc", 10)
    'abc'
    >>> len(middle_out("x" * 500, 60))
    60
    """
    # TODO: implement
    raise NotImplementedError


def truncate_tool_results(messages: list[Message], max_chars: int = 4_000) -> list[Message]:
    """Apply `middle_out` to the content of every `role: tool` message.

    Spec:
      * returns a NEW list; never mutate the input (the caller may still be holding it)
      * copy each modified message with `{**message, "content": ...}` so the original
        dict is untouched too
      * leave non-tool messages, and tool messages whose content is not a str, alone

    One unbounded tool result is the single fastest way to destroy a context window.
    A 2MB log file read is ~500,000 tokens.
    """
    # TODO: implement
    raise NotImplementedError
