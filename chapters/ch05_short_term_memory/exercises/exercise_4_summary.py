"""EXERCISE 4 — SummaryBuffer, with the two details that make it affordable.

    pytest chapters/ch05_short_term_memory/tests -q -k summary
"""

from __future__ import annotations

from typing import Callable

from agentlib.context import compact, message_pairs
from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens

from .exercise_3_strategies import MemoryStrategy


class SummaryBuffer(MemoryStrategy):
    """Old turns become a cached summary; recent turns stay verbatim.

    __init__(self, summarise, *, max_tokens, keep_recent=4, threshold=0.7,
             min_compact_groups=4)

    State to keep:
        self._summary: str | None = None      the cached summary text
        self._summarised_upto: int = 0        index into `messages` already folded in

    Note `min_compact_groups`: after a compaction the tail holds exactly `keep_recent`
    groups. One new message makes it keep_recent+1, and without this guard you would
    summarise again immediately, to remove a single message.

    build(messages):
      1. `tail = messages[self._summarised_upto:]`  — the part not yet summarised
         `view = self._with_summary(tail)`          — what you would actually send
      2. If estimate_messages_tokens(VIEW) <= max_tokens * threshold: return view.
         MEASURE THE VIEW, NOT `messages`. After the first compaction the full history
         is permanently over budget, so measuring it re-summarises on every turn
         forever — the exact cost trap this class exists to avoid.
      3. groups = message_pairs(tail)
         if len(groups) - keep_recent < min_compact_groups: return view
         i.e. do not spend an API call to fold one message away. Wait for a batch.
      4. Otherwise compact `tail`, passing a summariser that CARRIES THE OLD SUMMARY
         FORWARD:
             def summarise_with_carry(transcript):
                 if self._summary:
                     transcript = f"PREVIOUS SUMMARY:\\n{self._summary}\\n\\n{transcript}"
                 return self.summarise(transcript)
      5. compact() returns [marker] + recent. Extract the summary text out of the
         marker (strip the "[Summary of the earlier conversation]\\n" first line),
         cache it, and set
             self._summarised_upto = len(messages) - (len(compacted) - 1)
         so next turn only the genuinely new messages are considered.
      6. Return the compacted list.

    THE TWO DETAILS, and why they are the whole exercise:

    (a) THE CACHE. Summarising on every turn is a second quadratic on top of Chapter
        1's. Turn 10 summarises 9 turns, turn 11 summarises 10, turn 12 summarises 11.
        You can spend more summarising a conversation than you spent having it. The
        threshold + `_summarised_upto` pair means you summarise rarely.

    (b) THE CARRY-FORWARD. The second time you compact, the input no longer contains
        the first hour — it was already folded away. Without feeding the previous
        summary in, those facts are gone for good. With it, they degrade gradually,
        which is honest and survivable.
    """

    def __init__(
        self,
        summarise: Callable[[str], str],
        *,
        max_tokens: int,
        keep_recent: int = 4,
        threshold: float = 0.7,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    @property
    def summary(self) -> str | None:
        """The cached summary, or None if nothing has been compacted yet."""
        # TODO: implement
        raise NotImplementedError

    def build(self, messages: list[Message]) -> list[Message]:
        # TODO: implement
        raise NotImplementedError

    def _with_summary(self, tail: list[Message]) -> list[Message]:
        """Prepend the cached summary as a user message, if there is one.

        Returns `list(tail)` unchanged when there is no summary yet.
        """
        # TODO: implement
        raise NotImplementedError
