"""Token estimation — local, free, good enough for budgeting.

Promoted from Chapter 1, Exercise 1."""

from __future__ import annotations

import math

from agentlib.llm import Message

CHARS_PER_TOKEN = 4
PER_MESSAGE_OVERHEAD = 4
REPLY_PRIMING = 3


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[Message]) -> int:
    if not messages:
        return 0
    total = 0
    for message in messages:
        content = message.get("content") or ""   # `or ""` handles both None and missing
        total += estimate_tokens(content) + PER_MESSAGE_OVERHEAD
    return total + REPLY_PRIMING


def fits_in_budget(
    messages: list[Message],
    context_window: int,
    reserve_for_output: int = 1024,
) -> bool:
    return estimate_messages_tokens(messages) + reserve_for_output <= context_window
