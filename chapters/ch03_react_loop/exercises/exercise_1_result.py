"""EXERCISE 1 — The trace objects.

WHY: These four little classes decide whether your agent is improvable. An agent that
returns a string is a black box; one that returns a trace can be evaluated, profiled and
debugged. Build them before the loop, so the loop has somewhere to put its evidence.

    pytest chapters/ch03_react_loop/tests -q -k result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agentlib.conversation import Conversation
from agentlib.llm import LLMResponse, Message, Usage
from agentlib.tools import ToolCall


class StopReason(str, Enum):
    """Why the loop ended.

    Subclassing `str` means `StopReason.DONE == "done"` is True, which makes these
    painless to log, serialise to JSON and compare in tests.

    Members (value == lowercase name):
        DONE, MAX_STEPS, BUDGET, TIMEOUT, STOP_TOOL, ERROR
    """

    DONE = "done"
    MAX_STEPS = "max_steps"
    BUDGET = "budget"
    TIMEOUT = "timeout"
    STOP_TOOL = "stop_tool"
    ERROR = "error"


@dataclass
class Step:
    """One pass through the loop.

    Fields:
        index: int                       0-based
        response: LLMResponse
        tool_calls: list[ToolCall]       default empty
        tool_messages: list[Message]     default empty
        duration_s: float                default 0.0
    """

    index: int
    response: LLMResponse
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_messages: list[Message] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def used_tools(self) -> bool:
        """True if this step requested any tools."""
        # TODO: implement
        raise NotImplementedError

    @property
    def tool_names(self) -> list[str]:
        """Names of the tools requested in this step, in order."""
        # TODO: implement
        raise NotImplementedError


@dataclass
class AgentResult:
    """Everything that happened during a run.

    Fields:
        output: str
        stop_reason: StopReason
        steps: list[Step]                default empty
        conversation: Conversation|None  default None
        usage: Usage                     default Usage()
        cost: float                      default 0.0
        error: str | None                default None
    """

    output: str
    stop_reason: StopReason
    steps: list[Step] = field(default_factory=list)
    conversation: Conversation | None = None
    usage: Usage = field(default_factory=Usage)
    cost: float = 0.0
    error: str | None = None

    @property
    def step_count(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def succeeded(self) -> bool:
        """True only for DONE and STOP_TOOL.

        MAX_STEPS, BUDGET and TIMEOUT are failures even when `output` looks plausible —
        the agent was cut off, and what it produced is a partial answer wearing a
        confident tone. Treating them as success is how bad answers reach users.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def tool_sequence(self) -> list[str]:
        """Every tool called across every step, flattened, in order.

        The basis of trajectory evaluation (Chapter 11) and the fastest way to spot a
        pathology by eye: ['search', 'search', 'search', 'search'] tells you everything.
        """
        # TODO: implement
        raise NotImplementedError
