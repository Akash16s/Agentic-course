"""EXERCISE 3 — Subagents with isolated context.

WHY: The parent agent needs one fact from a 50k-token log. If it reads the log
itself, those 50k tokens sit in its window for the rest of the run and are paid for
on every later call. If a subagent reads it — in its own fresh conversation — the
parent receives three lines. Context isolation is the whole benefit; everything in
this file exists to protect it.

    pytest chapters/ch08b_harness/tests -q -k subagents
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agentlib.agent import Agent, AgentResult
from agentlib.context import middle_out
from agentlib.tools import Tool, ToolRegistry, build_tool

SUBAGENT_SYSTEM = (
    "You are a subagent. Another agent has given you one self-contained task. Do it "
    "with your tools, then reply with a short final answer: the result and the key "
    "evidence, no preamble. Your final message is the ONLY thing the other agent sees."
)


@dataclass
class SubagentResult:
    """What one delegation produced.

    Fields: task: str, output: str (the CONDENSED text the parent sees),
            stop_reason: str (a StopReason value, or "error"),
            steps: int = 0, tokens: int = 0, cost: float = 0.0, error: str|None = None
    """

    task: str
    output: str
    stop_reason: str
    steps: int = 0
    tokens: int = 0
    cost: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True when error is None AND stop_reason is "done" or "stop_tool"."""
        # TODO: implement
        raise NotImplementedError


def condense(result: AgentResult, max_chars: int) -> str:
    """Turn a child's whole AgentResult into the short text the parent sees.

    Spec:
      * text = result.output stripped; empty -> "(the subagent produced no output)"
      * cut it with `middle_out(text, max_chars)` (Chapter 4) — keeps start and end
      * if NOT result.succeeded, prefix
            f"[subagent stopped early: {result.stop_reason.value}] "
        (the prefix may push it slightly past max_chars; that is fine)

    The prefix is Chapter 3 and Chapter 8 in one line: a MAX_STEPS answer is a
    partial answer wearing a confident tone, and whoever reads it must be told.
    """
    # TODO: implement
    raise NotImplementedError


class SubagentRunner:
    """Run a task in a child Agent with a fresh conversation and restricted tools.

    __init__(self, client, tools: ToolRegistry, *, system=SUBAGENT_SYSTEM,
             model=None, max_steps=8, max_result_chars=2000, max_depth=1, depth=0,
             budget_usd=None, on_result=None)
        Store everything; self.results: list[SubagentResult] = []

    `tools` is the pool subagents may draw from (usually the parent's tools).
    `depth` is how deep the agent that OWNS this runner is: the top-level parent is
    0. With the default max_depth=1, the parent can delegate and children cannot.
    """

    def __init__(
        self,
        client: Any,
        tools: ToolRegistry,
        *,
        system: str = SUBAGENT_SYSTEM,
        model: str | None = None,
        max_steps: int = 8,
        max_result_chars: int = 2000,
        max_depth: int = 1,
        depth: int = 0,
        budget_usd: float | None = None,
        on_result: Callable[[SubagentResult], None] | None = None,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    @property
    def total_cost(self) -> float:
        """Sum of cost over self.results. Print this. Subagents multiply spend."""
        # TODO: implement
        raise NotImplementedError

    def restrict(self, names: list[str] | None) -> ToolRegistry:
        """Build the child's ToolRegistry.

        Spec:
          * names None -> every tool in self.tools; a list -> just those
          * "delegate" is ALWAYS dropped from that selection — a child only gets a
            delegate tool through the depth rule below, never by copying the parent's
          * any requested name not in self.tools -> ValueError listing the unknown
            names and the available ones
          * keep the order, drop duplicates
          * DEPTH RULE: if self.depth + 1 < self.max_depth, register a nested runner's
            tool: SubagentRunner(same config..., depth=self.depth + 1,
            on_result=self._record).as_tool()
        """
        # TODO: implement
        raise NotImplementedError

    def run(self, task: str, tools: list[str] | None = None) -> SubagentResult:
        """Delegate one task. NEVER RAISES.

        Algorithm:
          1. self.depth >= self.max_depth -> error result whose output mentions
             "depth" (stop_reason="error"). Do NOT call the model.
          2. registry = self.restrict(tools); ValueError -> error result with the
             message in `output`. Do NOT start the child.
          3. child = Agent(self.client, tools=registry, system=self.system,
                           model=self.model, max_steps=self.max_steps,
                           budget_usd=self.budget_usd)
          4. result = child.run(task)          <- pass the STRING.
             A string makes Agent build a brand-new Conversation(system, task).
             That single line IS the context isolation: the child cannot see the
             parent's history because nobody gave it to it.
             (Wrap it in try/except Exception -> error result, to be safe.)
          5. Return SubagentResult(task, output=condense(result, max_result_chars),
             stop_reason=result.stop_reason.value, steps=result.step_count,
             tokens=result.usage.total_tokens, cost=result.cost, error=result.error)

        EVERY result — success or error — goes through self._record(...), which
        appends it to self.results and calls on_result.
        """
        # TODO: implement
        raise NotImplementedError

    def _record(self, result: SubagentResult) -> SubagentResult:
        """Append to self.results, call self.on_result if set, return result."""
        # TODO: implement
        raise NotImplementedError

    def as_tool(self) -> Tool:
        """The `delegate` tool the parent calls.

        Define an inner function
            def delegate(task: str, tools: list[str] | None = None) -> str
        that returns `self.run(task, tools).output`, with an Args: section in its
        docstring, and return `build_tool(delegate, description=...)`.

        The description is a prompt, and it matters more than the code:
          * the subagent starts EMPTY and sees only the task text — say so, or the
            parent will write "look into that thing we discussed"
          * the parent gets the final answer back, not the working
          * list the tools a subagent can use (self.tools minus "delegate")
        """
        # TODO: implement
        raise NotImplementedError
