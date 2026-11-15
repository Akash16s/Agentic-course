"""EXERCISE 1 — Budget and prompt assembly.

    pytest chapters/ch04_context/tests -q -k budget
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens, estimate_tokens


@dataclass
class ContextBudget:
    """How the window is divided up.

    Fields (with these defaults):
        context_window: int = 128_000
        reserve_output: int = 4_096
        system_tokens:  int = 0
        tools_tokens:   int = 0
    """

    context_window: int = 128_000
    reserve_output: int = 4_096
    system_tokens: int = 0
    tools_tokens: int = 0

    @property
    def fixed(self) -> int:
        """system + tools + reserve_output — the part you cannot reclaim."""
        # TODO: implement
        raise NotImplementedError

    @property
    def available_for_history(self) -> int:
        """context_window - fixed.

        MAY BE NEGATIVE. Do not clamp it to zero: a negative number means the
        configuration itself is broken (more tools than window), and silently
        returning 0 hides that behind a confusing downstream error.
        """
        # TODO: implement
        raise NotImplementedError

    def fits(self, messages: list[Message]) -> bool:
        """True if these messages fit in `available_for_history`."""
        # TODO: implement
        raise NotImplementedError

    def headroom(self, messages: list[Message]) -> int:
        """available_for_history - estimated tokens. Negative when over."""
        # TODO: implement
        raise NotImplementedError

    @classmethod
    def measure(
        cls,
        *,
        context_window: int = 128_000,
        reserve_output: int = 4_096,
        system: str | None = None,
        tool_specs: list[dict[str, Any]] | None = None,
    ) -> "ContextBudget":
        """Build a budget by MEASURING the real system prompt and tool schemas.

        system_tokens = estimate_tokens(system or "")
        tools_tokens  = estimate_tokens(json.dumps(tool_specs)) if tool_specs else 0

        Serialising the specs to JSON is the right measure because that is literally
        what goes on the wire.
        """
        # TODO: implement
        raise NotImplementedError


@dataclass(order=True)
class Section:
    """One named chunk of a system prompt.

    `order=True` with `compare=False` on everything but `priority` means sections sort
    by priority alone.
    """

    priority: int
    name: str = field(compare=False)
    content: str = field(compare=False)
    required: bool = field(default=False, compare=False)


class PromptBuilder:
    """Assemble a system prompt from prioritised sections.

    LOWER priority number = MORE important = dropped LAST.
    """

    def __init__(self, separator: str = "\n\n") -> None:
        # TODO: implement
        raise NotImplementedError

    def add(self, name: str, content: str, *, priority: int = 50,
            required: bool = False) -> "PromptBuilder":
        """Add a section and return self for chaining.

        SKIP empty or whitespace-only content entirely — a conditional section that
        happens to be empty should not leave a blank gap in the prompt.
        Store `content.strip()`.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def names(self) -> list[str]:
        """Section names in render order (by priority)."""
        # TODO: implement
        raise NotImplementedError

    def render(self, max_tokens: int | None = None) -> str:
        """Join sections with `self.separator`, in priority order.

        With `max_tokens`: while the rendered text is too big, drop the
        HIGHEST-priority-number (least important) section that is not `required`.
        If only required sections remain and it still does not fit, return them anyway
        — better a clear API error than silently dropping your own rules.

        Sorting must be STABLE so that equal priorities keep insertion order.
        (`sorted` is stable in Python; do not use `list.sort(reverse=True)` tricks
        that break that.)
        """
        # TODO: implement
        raise NotImplementedError
