"""EXERCISE 4 — The Agent loop itself.

WHY: This is the chapter. Everything else was scaffolding for these forty lines.

    pytest chapters/ch03_react_loop/tests -q -k agent
"""

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
    """A model + tools + a loop."""

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
        """Store the configuration and build `self.tracker = CostTracker(budget_usd)`.

        `clock` is injected for the same reason `sleep` was in Chapter 1: so the
        timeout can be tested without actually waiting.
        """
        # TODO: implement
        raise NotImplementedError

    def run(self, task: str | Conversation) -> AgentResult:
        """Run the loop to completion. NEVER RAISES — failures come back in the result.

        Algorithm:

        1. Build the conversation:
             - a `Conversation`  -> use `task.copy()` (never mutate the caller's object)
             - a `str`           -> `Conversation(self.system).add_user(task)`
        2. `specs = self.tools.specs() or None`
             `or None` matters: sending `tools=[]` is not the same as omitting it, and
             some providers reject an empty array.
        3. Record `started = self.clock()`, `steps = []`, `usage = Usage()`.
        4. Loop:
             a. `check_stop_conditions(steps, max_steps=..., elapsed_s=...,
                 timeout_s=..., spent_usd=self.tracker.total_cost,
                 budget_usd=self.tracker.budget_usd)`
                -> if it returns a reason, finish with it and the last text seen
             b. call the model via `chat_with_retry(self.client, conversation.messages,
                max_attempts=..., model=..., temperature=..., max_tokens=...,
                tools=specs)`
                -> on `errors.LLMError`, finish with StopReason.ERROR, error=str(exc),
                   KEEPING the steps collected so far
             c. `usage = usage + response.usage`
             d. `self.tracker.record(response)` -> on `errors.BudgetExceeded`, append
                the step, then finish with StopReason.BUDGET
             e. `conversation.add_response(response)`   <- BEFORE the tool results
             f. `calls = parse_tool_calls(response)`
             g. no calls -> append the step, finish with StopReason.DONE and
                `response.text`
             h. `run_tools(self.tools, calls, parallel=self.parallel_tools)`
                -> on `StopSignal`, finish with StopReason.STOP_TOOL and
                   `signal.output or response.text`
             i. store the tool messages on the step, append it, call `self.on_step(step)`,
                and `conversation.extend(messages)`

        5. Every exit builds the same `AgentResult`: output, stop_reason, steps,
           conversation, usage, cost=self.tracker.total_cost, error.

        A local `finish(reason, output="", error=None)` closure keeps this readable —
        there are six exits and you do not want six copies of the constructor call.
        """
        # TODO: implement
        raise NotImplementedError

    @staticmethod
    def _last_text(steps: list[Step]) -> str:
        """The most recent non-empty `response.text`, or "".

        Used when the loop is cut short: the user still deserves whatever the agent had
        managed to say.
        """
        # TODO: implement
        raise NotImplementedError
