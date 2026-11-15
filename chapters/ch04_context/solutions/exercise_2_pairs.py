"""SOLUTION — Chapter 4, Exercise 2."""

from __future__ import annotations

from agentlib.llm import Message


def message_pairs(messages: list[Message]) -> list[list[Message]]:
    """Group messages into atomic units that must not be split.

    An assistant message carrying `tool_calls` and the `role: tool` messages that
    answer it are ONE unit. Cut between them and the provider returns a 400: you have
    sent an answer to a question the model can see no record of asking.

    This is the single most common context-management bug, and it only shows up once
    conversations get long enough to trim — i.e. in production.
    """
    groups: list[list[Message]] = []
    current: list[Message] = []

    for message in messages:
        role = message.get("role")
        if role == "tool":
            if current:
                current.append(message)   # attach to the assistant call above
            else:
                groups.append([message])  # orphan already; keep it together anyway
            continue
        if current:
            groups.append(current)
        current = [message]
        if role != "assistant" or not message.get("tool_calls"):
            groups.append(current)
            current = []

    if current:
        groups.append(current)
    return groups
