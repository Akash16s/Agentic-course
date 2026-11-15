"""SOLUTION — Chapter 3, Exercise 4."""

from __future__ import annotations

import time
from typing import Any, Callable

from agentlib import errors
from agentlib.conversation import Conversation
from agentlib.cost import CostTracker
from agentlib.errors import StopSignal
from agentlib.llm import Usage
from agentlib.retry import chat_with_retry
from agentlib.tools import ToolRegistry, parse_tool_calls

from .exercise_1_result import AgentResult, Step, StopReason
from .exercise_2_stop import check_stop_conditions
from .exercise_3_parallel import run_tools


class Agent:
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

    def run(self, task: str | Conversation) -> AgentResult:
        conversation = (
            task.copy()
            if isinstance(task, Conversation)
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

        while True:
            stop = check_stop_conditions(
                steps,
                max_steps=self.max_steps,
                elapsed_s=self.clock() - started,
                timeout_s=self.timeout_s,
                spent_usd=self.tracker.total_cost,
                budget_usd=self.tracker.budget_usd,
            )
            if stop is not None:
                return finish(stop, self._last_text(steps))

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
                # keep the steps: a partial trace is worth far more than none
                return finish(StopReason.ERROR, self._last_text(steps), error=str(exc))

            usage = usage + response.usage

            try:
                self.tracker.record(response)
            except errors.BudgetExceeded as exc:
                conversation.add_response(response)
                steps.append(
                    Step(len(steps), response, duration_s=self.clock() - step_started)
                )
                return finish(StopReason.BUDGET, response.text, error=str(exc))

            # BEFORE the tool results, always
            conversation.add_response(response)

            calls = parse_tool_calls(response)
            step = Step(
                index=len(steps),
                response=response,
                tool_calls=calls,
                duration_s=self.clock() - step_started,
            )

            if not calls:
                steps.append(step)
                self._emit(step)
                return finish(StopReason.DONE, response.text)

            try:
                messages = run_tools(self.tools, calls, parallel=self.parallel_tools)
            except StopSignal as signal:
                steps.append(step)
                self._emit(step)
                return finish(StopReason.STOP_TOOL, signal.output or response.text)

            step.tool_messages = messages
            steps.append(step)
            self._emit(step)
            conversation.extend(messages)

    def _emit(self, step: Step) -> None:
        if self.on_step is not None:
            self.on_step(step)

    @staticmethod
    def _last_text(steps: list[Step]) -> str:
        for step in reversed(steps):
            if step.response.text:
                return step.response.text
        return ""
