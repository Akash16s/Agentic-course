"""EXERCISE 3 — Memory strategies.

    pytest chapters/ch05_short_term_memory/tests -q -k strategies
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentlib.context import trim_messages
from agentlib.llm import Message


class MemoryStrategy(ABC):
    """Decides what the model SEES, given everything that was said.

    The store keeps the record; the strategy produces the view. Because they are
    separate, you can change strategy without losing history, and replay an old
    conversation under a new strategy — which Chapter 11 needs.
    """

    @abstractmethod
    def build(self, messages: list[Message]) -> list[Message]:
        """Return the messages to send this turn."""


class FullHistory(MemoryStrategy):
    """Send everything.

    Return a COPY, not the input list. Every strategy returns something the caller may
    mutate freely; being inconsistent about that is a bug generator.
    """

    def build(self, messages: list[Message]) -> list[Message]:
        # TODO: implement
        raise NotImplementedError


class SlidingWindow(MemoryStrategy):
    """Chapter 4's `trim_messages` behind the strategy interface.

    __init__(self, max_tokens: int, *, keep_first: int = 1, keep_last: int = 6)

    `keep_first` defaults to 1 rather than 0 on purpose: in an agent the task is
    stated in turn 1, and an agent that forgets its own objective keeps working
    confidently on nothing.
    """

    def __init__(self, max_tokens: int, *, keep_first: int = 1, keep_last: int = 6) -> None:
        # TODO: implement
        raise NotImplementedError

    def build(self, messages: list[Message]) -> list[Message]:
        # TODO: implement
        raise NotImplementedError
