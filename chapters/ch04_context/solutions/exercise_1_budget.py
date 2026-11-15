"""SOLUTION — Chapter 4, Exercise 1."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens, estimate_tokens


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
