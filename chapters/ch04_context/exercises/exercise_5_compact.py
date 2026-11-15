"""EXERCISE 5 — Compaction.

    pytest chapters/ch04_context/tests -q -k compact
"""

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
    """Flatten messages into plain text a model can summarise.

    Spec — one line per message:
        "{ROLE_UPPERCASE}: {content}"
    with `content` falling back to "" when None or missing.

    If the message has `tool_calls`, append " [called: name1, name2]" to the content
    (after stripping). Without this the transcript shows an assistant turn that said
    nothing, and the summary loses the entire record of what the agent DID.

    Tool-call names live at message["tool_calls"][i]["function"]["name"].
    """
    # TODO: implement
    raise NotImplementedError


def compact(
    messages: list[Message],
    summarise: Callable[[str], str],
    *,
    keep_recent: int = 4,
) -> list[Message]:
    """Replace old groups with a summary, keep recent groups verbatim.

    Spec:
      1. groups = message_pairs(messages)
      2. len(groups) <= keep_recent -> return a copy of `messages` unchanged
         (nothing worth compacting; do not spend an API call to say so)
      3. old    = flattened groups[:-keep_recent]
         recent = flattened groups[-keep_recent:]
      4. summary = summarise(render_transcript(old))
      5. return [marker] + recent, where marker is:
             {"role": "user",
              "content": f"[Summary of the earlier conversation]\\n{summary}"}

    `summarise` is injected so this is testable with a stub and so you can choose a
    cheap model for it — summarisation does not need your best model, and doing it
    with your most expensive one is a classic avoidable cost.

    Why `user` and not `system`: mid-conversation system messages are ignored by some
    providers and rejected by others. A labelled user message works everywhere.
    """
    # TODO: implement
    raise NotImplementedError
