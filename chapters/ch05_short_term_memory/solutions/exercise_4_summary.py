"""SOLUTION — Chapter 5, Exercise 4."""

from __future__ import annotations

from typing import Callable

from agentlib.context import compact, message_pairs
from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens

from .exercise_3_strategies import MemoryStrategy


class SummaryBuffer(MemoryStrategy):
    """Compact once the history crosses a threshold, then cache the summary.

    The cache is what makes this affordable: without it you pay for a summarisation
    call on every single turn, which can cost more than the conversation it is saving.
    """

    def __init__(
        self,
        summarise: Callable[[str], str],
        *,
        max_tokens: int,
        keep_recent: int = 4,
        threshold: float = 0.7,
        min_compact_groups: int = 4,
    ) -> None:
        self.summarise = summarise
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.threshold = threshold
        self.min_compact_groups = min_compact_groups
        self._summary: str | None = None
        self._summarised_upto = 0   # index into `messages` already folded in

    @property
    def summary(self) -> str | None:
        return self._summary

    def build(self, messages: list[Message]) -> list[Message]:
        tail = messages[self._summarised_upto:]
        view = self._with_summary(tail)

        # Measure the VIEW, not the full history. After the first compaction the full
        # history is permanently over budget, so measuring it would re-summarise on
        # every single turn forever.
        if estimate_messages_tokens(view) <= self.max_tokens * self.threshold:
            return view

        # Don't pay for an API call to fold one message away. Wait for a batch.
        groups = message_pairs(tail)
        if len(groups) - self.keep_recent < self.min_compact_groups:
            return view

        def summarise_with_carry(transcript: str) -> str:
            if self._summary:
                transcript = f"PREVIOUS SUMMARY:\n{self._summary}\n\n{transcript}"
            return self.summarise(transcript)

        compacted = compact(tail, summarise_with_carry, keep_recent=self.keep_recent)
        # compacted[0] is the summary marker; everything after is verbatim recent
        self._summary = compacted[0]["content"].split("\n", 1)[-1]
        self._summarised_upto = len(messages) - (len(compacted) - 1)
        return compacted

    def _with_summary(self, tail: list[Message]) -> list[Message]:
        if not self._summary:
            return list(tail)
        marker: Message = {
            "role": "user",
            "content": f"[Summary of the earlier conversation]\n{self._summary}",
        }
        return [marker] + list(tail)
