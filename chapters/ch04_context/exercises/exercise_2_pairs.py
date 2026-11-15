"""EXERCISE 2 — Grouping messages into atomic units.

WHY: This is the most load-bearing function in the chapter. Cut a conversation between
an assistant's `tool_calls` and the `tool` messages answering them, and the provider
returns a 400. It never happens in development, because short conversations never get
trimmed. It happens the first day a real user has a long session.

    pytest chapters/ch04_context/tests -q -k pairs
"""

from __future__ import annotations

from agentlib.llm import Message


def message_pairs(messages: list[Message]) -> list[list[Message]]:
    """Group messages into units that must never be split.

    Rules:
      * a `user` message              -> its own group
      * an `assistant` message with NO tool_calls   -> its own group
      * an `assistant` message WITH tool_calls      -> starts a group; every
        immediately-following `tool` message joins it
      * a `tool` message with no assistant above it (already orphaned, e.g. someone
        else sliced the list) -> its own group, so we at least do not make it worse
      * a `system` message            -> its own group

    Order must be preserved, and flattening the result must reproduce the input
    exactly. That is the invariant to test against.

    Example:
        [user, assistant(tool_calls=[c1,c2]), tool(c1), tool(c2), assistant, user]
     -> [[user], [assistant, tool, tool], [assistant], [user]]
    """
    # TODO: implement
    raise NotImplementedError
