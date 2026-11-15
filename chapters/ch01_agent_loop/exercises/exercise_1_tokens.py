"""EXERCISE 1 — Token estimation.

WHY: You cannot budget what you cannot measure, and you cannot afford an API round trip
every time you want to know "will this fit?". A local estimate that is right to within
~15% is worth far more than an exact count that costs a network call.

This estimate is for BUDGETING (will it fit? should I trim?).
It is never for BILLING — bill from `response.usage`, which is ground truth.

Run the tests:
    pytest chapters/ch01_agent_loop/tests -q -k tokens
"""

from __future__ import annotations

import math

from agentlib.llm import Message

#: ~4 characters per token holds for English prose. Code and non-Latin scripts are
#: denser (more tokens per character), so this under-estimates them. Be aware of it.
CHARS_PER_TOKEN = 4

#: Every message carries structural overhead on the wire: the role, the delimiters the
#: model's chat template inserts. Roughly 4 tokens per message across model families.
PER_MESSAGE_OVERHEAD = 4

#: The template also appends a short "now you speak, assistant" primer before generation.
REPLY_PRIMING = 3


def estimate_tokens(text: str) -> int:
    """Estimate how many tokens `text` will become.

    Spec:
      * "" -> 0
      * otherwise -> ceil(len(text) / CHARS_PER_TOKEN)

    Use math.ceil, not round: it is better to over-estimate your context usage than to
    discover at request time that you went over.

    >>> estimate_tokens("")
    0
    >>> estimate_tokens("abcd")
    1
    >>> estimate_tokens("abcde")
    2
    """
    # TODO: implement
    raise NotImplementedError


def estimate_messages_tokens(messages: list[Message]) -> int:
    """Estimate the total prompt tokens for a whole message list.

    Spec:
      * [] -> 0
      * otherwise: sum over messages of
            estimate_tokens(content) + PER_MESSAGE_OVERHEAD
        plus REPLY_PRIMING once, for the whole request.

    A message may have `content` of None (that happens with tool calls, Chapter 2).
    Treat None as "".

    >>> estimate_messages_tokens([])
    0
    >>> estimate_messages_tokens([{"role": "user", "content": "abcd"}])
    8
    """
    # TODO: implement
    raise NotImplementedError


def fits_in_budget(
    messages: list[Message],
    context_window: int,
    reserve_for_output: int = 1024,
) -> bool:
    """Will this request fit, leaving room for the model's answer?

    The trap this function exists to prevent: the context window is shared between your
    input AND the generated output. A 200k window with a 199k prompt gives the model
    1k tokens to reply in. Always reserve.

    Spec: True if
        estimate_messages_tokens(messages) + reserve_for_output <= context_window

    >>> fits_in_budget([{"role": "user", "content": "hi"}], 100, reserve_for_output=10)
    True
    >>> fits_in_budget([{"role": "user", "content": "x" * 4000}], 100)
    False
    """
    # TODO: implement
    raise NotImplementedError
