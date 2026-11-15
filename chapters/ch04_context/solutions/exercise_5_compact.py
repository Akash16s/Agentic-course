"""SOLUTION — Chapter 4, Exercise 5."""

from __future__ import annotations

from typing import Callable

from agentlib.llm import Message

from .exercise_2_pairs import message_pairs


COMPACTION_PROMPT = """\
Summarise the conversation below so that another assistant can continue it with no \
other information.

Preserve, in this order of importance:
1. The user's goal and any constraints they stated
2. Decisions made and facts established (names, ids, paths, numbers, URLs)
3. What has already been tried and what the result was
4. What is still outstanding

Drop pleasantries, restatements and reasoning that led nowhere. Write plain prose, \
under 400 words. Do not address the user.

CONVERSATION:
{transcript}"""


def render_transcript(messages: list[Message]) -> str:
    """Flatten messages into text a model can summarise."""
    lines = []
    for message in messages:
        role = message.get("role", "?")
        content = message.get("content") or ""
        if message.get("tool_calls"):
            names = ", ".join(
                c.get("function", {}).get("name", "?") for c in message["tool_calls"]
            )
            content = (content + f" [called: {names}]").strip()
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def compact(
    messages: list[Message],
    summarise: Callable[[str], str],
    *,
    keep_recent: int = 4,
) -> list[Message]:
    """Replace old turns with a summary, keeping the most recent groups verbatim.

    Returns a NEW list: [user(summary marker)] + recent groups.

    Why a `user` message and not a `system` one: mid-conversation system messages
    confuse some providers and get ignored by others. A user message labelled as a
    summary is understood everywhere.
    """
    groups = message_pairs(messages)
    if len(groups) <= keep_recent:
        return list(messages)

    old = [m for g in groups[: len(groups) - keep_recent] for m in g]
    recent = [m for g in groups[len(groups) - keep_recent:] for m in g]

    summary = summarise(render_transcript(old))
    marker: Message = {
        "role": "user",
        "content": f"[Summary of the earlier conversation]\n{summary}",
    }
    return [marker] + recent
