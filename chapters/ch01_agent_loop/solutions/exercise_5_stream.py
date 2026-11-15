"""SOLUTION — Exercise 5."""

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
    pieces: list[str] = []          # list + join: O(n), not O(n^2)
    finish_reason = "stop"
    prompt_tokens = 0
    completion_tokens = 0
    model = ""

    for chunk in client.stream_raw(messages, **chat_kwargs):
        # getattr with a default: real SDK chunks and our fakes both work, and a
        # provider that omits a field does not crash the loop.
        choices = getattr(chunk, "choices", None) or []
        if choices:
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if content:
                pieces.append(content)
                if on_delta is not None:
                    on_delta(content)
            if getattr(choices[0], "finish_reason", None):
                finish_reason = choices[0].finish_reason

        usage = getattr(chunk, "usage", None)
        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0

        model = getattr(chunk, "model", "") or model

    return LLMResponse(
        text="".join(pieces),
        finish_reason=finish_reason,
        usage=Usage(prompt_tokens, completion_tokens),
        model=model,
    )


def print_stream(client: Any, messages: list[Message], **chat_kwargs: Any) -> LLMResponse:
    response = stream_chat(
        client,
        messages,
        on_delta=lambda piece: print(piece, end="", flush=True),
        **chat_kwargs,
    )
    print()
    return response
