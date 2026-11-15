"""EXERCISE 5 — Streaming.

WHY: Generation is sequential — roughly 10-50ms PER OUTPUT TOKEN. An 800-token answer
takes ~20 seconds and no amount of bandwidth changes that. Streaming does not make it
faster; it makes the wait visible instead of dead. Time-to-first-token drops from 20s to
under a second, and perceived quality goes up enormously.

The mechanics: instead of one JSON response, the server holds the connection open and
sends server-sent events, each carrying a small `delta`. You accumulate them.

Three wrinkles that trip people up, and the reason this is an exercise rather than a
paragraph:

  1. Some chunks have an EMPTY `choices` list (the usage-only final chunk).
  2. `delta.content` is often None — role-announcement chunks, tool-call chunks.
  3. `usage` only arrives at the very end, if you asked for it. You must not assume it
     is on the first chunk.

Run the tests:
    pytest chapters/ch01_agent_loop/tests -q -k stream
"""

from __future__ import annotations

from typing import Any, Callable

from agentlib.llm import LLMResponse, Message, Usage


def stream_chat(
    client: Any,
    messages: list[Message],
    *,
    on_delta: Callable[[str], None] | None = None,
    **chat_kwargs: Any,
) -> LLMResponse:
    """Consume `client.stream_raw(messages, **chat_kwargs)` and return a complete
    `LLMResponse`, calling `on_delta(piece)` for each text fragment as it arrives.

    Spec — iterate the chunks and for each one:
      * if `chunk.choices` is non-empty:
          - `content = chunk.choices[0].delta.content`; if it is a non-empty string,
            append it to the accumulated text and call `on_delta(content)`
          - if `chunk.choices[0].finish_reason` is truthy, remember it
      * if `chunk.usage` is not None, remember prompt_tokens / completion_tokens
      * remember `chunk.model` if present

    Return an LLMResponse with the joined text, the finish_reason (default "stop"),
    the Usage (zeros if none arrived) and the model.

    Performance note: build the text with a list and "".join() at the end, not
    `text += piece`. Repeated string concatenation is O(n^2), and a long stream is
    thousands of pieces. It matters more than you would guess.
    """
    # TODO: implement
    raise NotImplementedError


def print_stream(client: Any, messages: list[Message], **chat_kwargs: Any) -> LLMResponse:
    """Convenience: stream to stdout as it arrives, then return the full response.

    Use `print(piece, end="", flush=True)` — without `flush=True` Python buffers the
    output and you get the whole answer at once, which defeats the entire point and is
    a genuinely common bug.
    """
    # TODO: implement
    raise NotImplementedError
