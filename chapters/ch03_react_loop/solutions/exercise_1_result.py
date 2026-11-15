"""SOLUTION — Chapter 3, Exercise 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agentlib.conversation import Conversation
from agentlib.llm import LLMResponse, Message, Usage
from agentlib.tools import ToolCall


class StopReason(str, Enum):
    DONE = "done"
    MAX_STEPS = "max_steps"
    BUDGET = "budget"
    TIMEOUT = "timeout"
    STOP_TOOL = "stop_tool"
    ERROR = "error"


@dataclass
class Step:
    index: int
    response: LLMResponse
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_messages: list[Message] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def used_tools(self) -> bool:
        return bool(self.tool_calls)

    @property
    def tool_names(self) -> list[str]:
        return [c.name for c in self.tool_calls]


@dataclass
class AgentResult:
    output: str
    stop_reason: StopReason
    steps: list[Step] = field(default_factory=list)
    conversation: Conversation | None = None
    usage: Usage = field(default_factory=Usage)
    cost: float = 0.0
    error: str | None = None

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def succeeded(self) -> bool:
        return self.stop_reason in (StopReason.DONE, StopReason.STOP_TOOL)

    @property
    def tool_sequence(self) -> list[str]:
        return [name for step in self.steps for name in step.tool_names]

    def __str__(self) -> str:
        return (
            f"AgentResult({self.stop_reason.value}, {self.step_count} steps, "
            f"${self.cost:.4f}, {self.usage.total_tokens} tokens)"
        )
