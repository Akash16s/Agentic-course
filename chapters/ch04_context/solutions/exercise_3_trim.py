"""SOLUTION — Chapter 4, Exercise 3."""

from __future__ import annotations

from typing import Iterable

from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens

from .exercise_2_pairs import message_pairs


def trim_messages(
    messages: list[Message],
    max_tokens: int,
    *,
    keep_first: int = 0,
    keep_last: int = 1,
) -> list[Message]:
    """Drop whole groups from the middle-front until the list fits.

    `keep_first` protects the opening turns (often the actual task statement).
    `keep_last` protects the most recent groups, which carry the current state.
    Both are counted in GROUPS, not messages.
    """
    groups = message_pairs(messages)
    if not groups:
        return []

    # Clamp so head and tail cannot overlap. Without this, a short conversation with
    # keep_first=1, keep_last=6 and only 2 groups returns group 0 TWICE.
    keep_first = max(0, min(keep_first, len(groups)))
    keep_last = max(0, min(keep_last, len(groups) - keep_first))

    head = groups[:keep_first]
    tail = groups[len(groups) - keep_last:] if keep_last else []
    middle = groups[keep_first: len(groups) - keep_last]

    def flatten(gs: Iterable[list[Message]]) -> list[Message]:
        return [m for g in gs for m in g]

    while middle and estimate_messages_tokens(
        flatten(head + middle + tail)
    ) > max_tokens:
        middle.pop(0)   # oldest middle group goes first

    return flatten(head + middle + tail)
