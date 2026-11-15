"""Context engineering — deciding what goes in the window and what gets thrown away.

Promoted from Chapter 4.

The context window is the scarcest resource in an agent. Everything here is about
spending it deliberately instead of letting it fill up and explode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens, estimate_tokens

# --------------------------------------------------------------------- budget


@dataclass
class ContextBudget:
    """How the window is divided up.

    The window is shared between everything you send AND everything the model
    generates. People forget the second half and then wonder why a 200k-context model
    produced two sentences.
    """

    context_window: int = 128_000
    reserve_output: int = 4_096
    system_tokens: int = 0
    tools_tokens: int = 0

    @property
    def fixed(self) -> int:
        """Tokens you cannot reclaim: system prompt + tool schemas + output reserve."""
        return self.system_tokens + self.tools_tokens + self.reserve_output

    @property
    def available_for_history(self) -> int:
        """What is left for the conversation. Can go negative — that is a real
        configuration, and a broken one."""
        return self.context_window - self.fixed

    def fits(self, messages: list[Message]) -> bool:
        return estimate_messages_tokens(messages) <= self.available_for_history

    def headroom(self, messages: list[Message]) -> int:
        return self.available_for_history - estimate_messages_tokens(messages)

    @classmethod
    def measure(
        cls,
        *,
        context_window: int = 128_000,
        reserve_output: int = 4_096,
        system: str | None = None,
        tool_specs: list[dict[str, Any]] | None = None,
    ) -> "ContextBudget":
        """Build a budget by measuring the actual system prompt and tool schemas."""
        import json

        tools_tokens = (
            estimate_tokens(json.dumps(tool_specs)) if tool_specs else 0
        )
        return cls(
            context_window=context_window,
            reserve_output=reserve_output,
            system_tokens=estimate_tokens(system or ""),
            tools_tokens=tools_tokens,
        )


# -------------------------------------------------------------- prompt builder


@dataclass(order=True)
class Section:
    priority: int
    name: str = field(compare=False)
    content: str = field(compare=False)
    required: bool = field(default=False, compare=False)


class PromptBuilder:
    """Assemble a system prompt out of named, prioritised sections.

    Why bother instead of an f-string? Because in a real agent the system prompt is
    assembled from parts that appear conditionally (user profile, retrieved memories,
    today's date, tool guidance), and each has a different claim on the budget. When
    space runs out you want to drop the least important section, not truncate the
    middle of a sentence.

    Lower `priority` number = more important = dropped last.
    """

    def __init__(self, separator: str = "\n\n") -> None:
        self._sections: list[Section] = []
        self.separator = separator

    def add(self, name: str, content: str, *, priority: int = 50,
            required: bool = False) -> "PromptBuilder":
        if content and content.strip():
            self._sections.append(Section(priority, name, content.strip(), required))
        return self

    @property
    def names(self) -> list[str]:
        return [s.name for s in self._ordered()]

    def _ordered(self) -> list[Section]:
        # stable sort: equal priorities keep insertion order
        return sorted(self._sections, key=lambda s: s.priority)

    def render(self, max_tokens: int | None = None) -> str:
        """Join the sections. If `max_tokens` is set, drop the lowest-priority
        non-required sections until it fits."""
        sections = self._ordered()
        if max_tokens is None:
            return self.separator.join(s.content for s in sections)

        while sections:
            text = self.separator.join(s.content for s in sections)
            if estimate_tokens(text) <= max_tokens:
                return text
            droppable = [s for s in sections if not s.required]
            if not droppable:
                return text  # everything left is required; send it and let the API complain
            worst = max(droppable, key=lambda s: s.priority)
            sections.remove(worst)
        return ""


# ------------------------------------------------------------------- trimming


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


def trim_messages(
    messages: list[Message],
    max_tokens: int,
    *,
    keep_first: int = 0,
    keep_last: int = 1,
) -> list[Message]:
    """Drop whole groups from the middle-front until the list fits.

    `keep_first` protects the opening turns (often the actual task statement).
    `keep_last` protects the most recent groups, which carry the current state.
    Both are counted in GROUPS, not messages.
    """
    groups = message_pairs(messages)
    if not groups:
        return []

    # Clamp so head and tail cannot overlap. Without this, a short conversation with
    # keep_first=1, keep_last=6 and only 2 groups returns group 0 TWICE.
    keep_first = max(0, min(keep_first, len(groups)))
    keep_last = max(0, min(keep_last, len(groups) - keep_first))

    head = groups[:keep_first]
    tail = groups[len(groups) - keep_last:] if keep_last else []
    middle = groups[keep_first: len(groups) - keep_last]

    def flatten(gs: Iterable[list[Message]]) -> list[Message]:
        return [m for g in gs for m in g]

    while middle and estimate_messages_tokens(
        flatten(head + middle + tail)
    ) > max_tokens:
        middle.pop(0)   # oldest middle group goes first

    return flatten(head + middle + tail)


#: Shorter than it looks tempting to make it — every character here is a character of
#: real content you are throwing away.
MIDDLE_MARKER = "\n...[{n} chars cut]...\n"


def middle_out(text: str, max_chars: int, marker: str = MIDDLE_MARKER) -> str:
    """Keep the start and the end, cut the middle.

    For tool output — a stack trace, a long file, a big JSON blob — the beginning and
    the end carry most of the signal and the middle is filler. Plain truncation throws
    away the end, which is usually exactly where the error message is.

    If `max_chars` is so small that the marker would dominate, falls back to plain
    truncation: a marker with two characters of content either side helps nobody.
    """
    if len(text) <= max_chars:
        return text

    note = marker.format(n=len(text) - max_chars)
    keep = max_chars - len(note)
    if keep < 8:
        return text[:max_chars]

    head = keep // 2
    tail = keep - head
    return text[:head] + marker.format(n=len(text) - keep) + text[-tail:]


def truncate_tool_results(messages: list[Message], max_chars: int = 4_000) -> list[Message]:
    """Cap every tool result. One unbounded tool return can eat a whole window."""
    out: list[Message] = []
    for message in messages:
        if message.get("role") == "tool" and isinstance(message.get("content"), str):
            message = {**message, "content": middle_out(message["content"], max_chars)}
        out.append(message)
    return out


# ------------------------------------------------------------------ compaction

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
