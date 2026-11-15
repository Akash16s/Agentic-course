"""The agent loop.

Promoted from Chapter 3.

Everything before this chapter was parts. This is the engine: think, decide, act,
observe, repeat — with the stop conditions that keep it from running forever.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from agentlib import errors
from agentlib.errors import StopSignal
from agentlib.conversation import Conversation
from agentlib.cost import CostTracker
from agentlib.llm import LLMResponse, Message, Usage
from agentlib.retry import chat_with_retry
from agentlib.tools import (
    ToolCall,
    ToolRegistry,
    parse_tool_calls,
    tool_result_message,
)


class StopReason(str, Enum):
    """Why the loop ended. Log this. An agent that always stops for the same
    unexpected reason is telling you something."""

    DONE = "done"                 # the model answered with no tool calls: success
    MAX_STEPS = "max_steps"       # hit the step budget: usually a stuck agent
    BUDGET = "budget"             # hit the spend limit
    TIMEOUT = "timeout"           # hit the wall-clock limit
    STOP_TOOL = "stop_tool"       # a tool declared the task complete
    ERROR = "error"               # an unrecoverable failure


@dataclass
class Step:
    """One pass through the loop. The unit of an agent trace."""

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
    """Everything that happened, not just the answer.

    Returning only `output` is the single most common design mistake in agent code.
    You cannot evaluate (ch 10-11), trace (ch 12) or debug (always) an agent whose
    run() gives you a string.
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
        return len(self.steps)

    @property
    def succeeded(self) -> bool:
        return self.stop_reason in (StopReason.DONE, StopReason.STOP_TOOL)

    @property
    def tool_sequence(self) -> list[str]:
        """Flat list of every tool called, in order. The basis of trajectory evals."""
        return [name for step in self.steps for name in step.tool_names]

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"AgentResult({self.stop_reason.value}, {self.step_count} steps, "
            f"${self.cost:.4f}, {self.usage.total_tokens} tokens)"
        )


class Agent:
    """A model + tools + a loop.

    >>> agent = Agent(client, tools=registry, system="You are helpful.")
    >>> result = agent.run("what is 2+2?")
    >>> result.output
    '4'
    """

    def __init__(
        self,
        client: Any,
        *,
        tools: ToolRegistry | None = None,
        system: str | None = None,
        model: str | None = None,
        max_steps: int = 10,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        budget_usd: float | None = None,
        timeout_s: float | None = None,
        parallel_tools: bool = True,
        max_attempts: int = 3,
        on_step: Callable[[Step], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        # `tools or ToolRegistry()` would discard an empty registry that was
        # deliberately passed in — ToolRegistry defines __len__, so it is falsy.
        self.tools = tools if tools is not None else ToolRegistry()
        self.system = system
        self.model = model
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.parallel_tools = parallel_tools
        self.max_attempts = max_attempts
        self.on_step = on_step
        self.clock = clock
        self.tracker = CostTracker(budget_usd=budget_usd)

    # ------------------------------------------------------------------ run

    def run(self, task: str | Conversation) -> AgentResult:
        conversation = (
            task.copy() if isinstance(task, Conversation)
            else Conversation(self.system).add_user(task)
        )
        steps: list[Step] = []
        usage = Usage()
        started = self.clock()
        specs = self.tools.specs() or None

        def finish(reason: StopReason, output: str = "", error: str | None = None):
            return AgentResult(
                output=output,
                stop_reason=reason,
                steps=steps,
                conversation=conversation,
                usage=usage,
                cost=self.tracker.total_cost,
                error=error,
            )

        for index in range(self.max_steps):
            if self.timeout_s is not None and self.clock() - started > self.timeout_s:
                return finish(StopReason.TIMEOUT, self._last_text(steps))

            step_started = self.clock()
            try:
                response = chat_with_retry(
                    self.client,
                    conversation.messages,
                    max_attempts=self.max_attempts,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    tools=specs,
                )
            except errors.LLMError as exc:
                return finish(StopReason.ERROR, self._last_text(steps), error=str(exc))

            usage = usage + response.usage
            try:
                self.tracker.record(response)
            except errors.BudgetExceeded as exc:
                conversation.add_response(response)
                steps.append(Step(index, response, duration_s=self.clock() - step_started))
                return finish(StopReason.BUDGET, response.text, error=str(exc))

            conversation.add_response(response)
            calls = parse_tool_calls(response)
            step = Step(index, response, tool_calls=calls,
                        duration_s=self.clock() - step_started)

            # No tools requested -> the model is answering. That is the exit.
            if not calls:
                steps.append(step)
                self._emit(step)
                return finish(StopReason.DONE, response.text)

            try:
                messages = self._run_tools(calls)
            except StopSignal as signal:
                steps.append(step)
                self._emit(step)
                return finish(StopReason.STOP_TOOL, signal.output or response.text)

            step.tool_messages = messages
            steps.append(step)
            self._emit(step)
            conversation.extend(messages)

        return finish(StopReason.MAX_STEPS, self._last_text(steps))

    # -------------------------------------------------------------- helpers

    def _run_tools(self, calls: list[ToolCall]) -> list[Message]:
        """Execute calls, preserving order. StopSignal is allowed to escape."""
        if not self.parallel_tools or len(calls) == 1:
            return [self._run_one(c) for c in calls]

        with ThreadPoolExecutor(max_workers=min(8, len(calls))) as pool:
            # map() preserves input order, which the tool_call_ids depend on
            return list(pool.map(self._run_one, calls))

    def _run_one(self, call: ToolCall) -> Message:
        # StopSignal propagates out of Tool.call by design; _run_tools lets it fly.
        return tool_result_message(call, self.tools.execute(call.name, call.arguments))

    def _emit(self, step: Step) -> None:
        if self.on_step is not None:
            self.on_step(step)

    @staticmethod
    def _last_text(steps: list[Step]) -> str:
        for step in reversed(steps):
            if step.response.text:
                return step.response.text
        return ""
