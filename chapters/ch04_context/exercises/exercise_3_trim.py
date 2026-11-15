"""EXERCISE 3 — Group-aware trimming.

    pytest chapters/ch04_context/tests -q -k trim
"""

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
    """Drop whole GROUPS from the front of the middle until the list fits.

    `keep_first` and `keep_last` are counts of GROUPS, not messages.

    Spec:
      1. groups = message_pairs(messages); [] -> []
      1b. CLAMP so head and tail cannot overlap:
             keep_first = max(0, min(keep_first, len(groups)))
             keep_last  = max(0, min(keep_last, len(groups) - keep_first))
          Without this, 2 groups with keep_first=1 and keep_last=6 returns group 0
          TWICE — a duplicated message the model reads as the user repeating itself.
      2. head   = the first `keep_first` groups          (protected)
         tail   = the last  `keep_last`  groups          (protected)
         middle = everything between them
      3. while middle is non-empty AND the flattened head+middle+tail is over
         `max_tokens`: drop middle[0] (the oldest unprotected group)
      4. return the flattened result

    Note what this does NOT do: it never drops a protected group, so the result can
    still exceed max_tokens. That is deliberate. Returning something over budget and
    letting the API say so is better than silently deleting the user's task statement.

    Why keep_first matters for agents specifically: the task is stated in turn 1. A
    pure sliding window eventually drops it and the agent forgets its own objective
    while still confidently doing *something*.
    """
    # TODO: implement
    raise NotImplementedError
