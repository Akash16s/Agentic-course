"""SOLUTION — Chapter 5, Exercise 3."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentlib.context import trim_messages
from agentlib.llm import Message


class MemoryStrategy(ABC):
    """Decides what the model SEES, given everything that was said.

    Storage keeps the full record; the strategy produces the view. Keeping these
    separate means you can change the strategy without losing history, and replay an
    old conversation under a new strategy — which you will want in Chapter 11.
    """

    @abstractmethod
    def build(self, messages: list[Message]) -> list[Message]: ...


class FullHistory(MemoryStrategy):
    """Send everything. Correct until it isn't."""

    def build(self, messages: list[Message]) -> list[Message]:
        return list(messages)


class SlidingWindow(MemoryStrategy):
    """Keep the first `keep_first` and last `keep_last` groups within a token budget."""

    def __init__(self, max_tokens: int, *, keep_first: int = 1, keep_last: int = 6) -> None:
        self.max_tokens = max_tokens
        self.keep_first = keep_first
        self.keep_last = keep_last

    def build(self, messages: list[Message]) -> list[Message]:
        return trim_messages(
            messages,
            self.max_tokens,
            keep_first=self.keep_first,
            keep_last=self.keep_last,
        )
