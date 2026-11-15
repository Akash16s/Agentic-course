"""SOLUTION — Chapter 17, Exercise 1."""

from __future__ import annotations

from typing import Any

START = "__start__"
END = "__end__"


def replace(current: Any, update: Any) -> Any:
    """Default reducer: the update wins."""
    return update


def append(current: Any, update: Any) -> Any:
    """Accumulate lists. This is how `messages` works in every graph framework.

    Without it, every node that touches `messages` would have to read the whole
    list, copy it, append, and return it — and any node that forgot would silently
    wipe the conversation.
    """
    if current is None:
        return list(update) if isinstance(update, list) else [update]
    if isinstance(update, list):
        return list(current) + update
    return list(current) + [update]


def add(current: Any, update: Any) -> Any:
    """Accumulate numbers — step counts, costs, token totals."""
    return (current or 0) + update
