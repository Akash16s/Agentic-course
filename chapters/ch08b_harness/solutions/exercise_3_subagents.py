"""SOLUTION — Chapter 8b, Exercise 3."""

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
    task: str
    output: str
    stop_reason: str
    steps: int = 0
    tokens: int = 0
    cost: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.stop_reason in ("done", "stop_tool")


def condense(result: AgentResult, max_chars: int) -> str:
    text = (result.output or "").strip() or "(the subagent produced no output)"
    text = middle_out(text, max_chars)
    if not result.succeeded:
        text = f"[subagent stopped early: {result.stop_reason.value}] {text}"
    return text


class SubagentRunner:
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
        self.client = client
        self.tools = tools
        self.system = system
        self.model = model
        self.max_steps = max_steps
        self.max_result_chars = max_result_chars
        self.max_depth = max_depth
        self.depth = depth
        self.budget_usd = budget_usd
        self.on_result = on_result
        self.results: list[SubagentResult] = []

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self.results)

    def restrict(self, names: list[str] | None) -> ToolRegistry:
        if names is None:
            wanted = [n for n in self.tools.names if n != "delegate"]
        else:
            wanted = [n for n in names if n != "delegate"]
        unknown = [n for n in wanted if n not in self.tools]
        if unknown:
            raise ValueError(
                f"unknown tools {unknown}. Available: {', '.join(self.tools.names)}"
            )
        registry = ToolRegistry([self.tools.get(n) for n in dict.fromkeys(wanted)])
        if self.depth + 1 < self.max_depth:
            child = SubagentRunner(
                self.client, self.tools, system=self.system, model=self.model,
                max_steps=self.max_steps, max_result_chars=self.max_result_chars,
                max_depth=self.max_depth, depth=self.depth + 1,
                budget_usd=self.budget_usd, on_result=self._record,
            )
            registry.register(child.as_tool())
        return registry

    def run(self, task: str, tools: list[str] | None = None) -> SubagentResult:
        if self.depth >= self.max_depth:
            return self._record(SubagentResult(
                task, "error: maximum delegation depth reached; do the task yourself",
                stop_reason="error", error="max depth"))
        try:
            registry = self.restrict(tools)
        except ValueError as exc:
            return self._record(SubagentResult(task, f"error: {exc}",
                                               stop_reason="error", error=str(exc)))
        child = Agent(
            self.client, tools=registry, system=self.system, model=self.model,
            max_steps=self.max_steps, budget_usd=self.budget_usd,
        )
        try:
            result = child.run(task)
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            return self._record(SubagentResult(task, f"error: {msg}",
                                               stop_reason="error", error=msg))
        return self._record(SubagentResult(
            task=task,
            output=condense(result, self.max_result_chars),
            stop_reason=result.stop_reason.value,
            steps=result.step_count,
            tokens=result.usage.total_tokens,
            cost=result.cost,
            error=result.error,
        ))

    def _record(self, result: SubagentResult) -> SubagentResult:
        self.results.append(result)
        if self.on_result is not None:
            self.on_result(result)
        return result

    def as_tool(self) -> Tool:
        available = [n for n in self.tools.names if n != "delegate"]

        def delegate(task: str, tools: list[str] | None = None) -> str:
            """Delegate a self-contained task.

            Args:
                task: everything the subagent needs to know; it sees nothing else
                tools: names of the tools it may use (omit for all)
            """
            return self.run(task, tools).output

        return build_tool(delegate, description=(
            "Delegate a self-contained subtask to a subagent with a fresh, empty "
            "context. It sees ONLY the task text you write, so include every detail "
            "it needs. You get back its final answer, not its working. Use it for "
            "searches and reads that would otherwise flood your context. "
            f"Tools a subagent can use: {', '.join(available) or 'none'}."
        ))
