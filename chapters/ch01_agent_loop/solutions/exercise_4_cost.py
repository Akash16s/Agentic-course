"""SOLUTION — Exercise 4."""

from __future__ import annotations

from dataclasses import dataclass

from agentlib.errors import BudgetExceeded
from agentlib.llm import LLMResponse
from agentlib.pricing import cost_usd


@dataclass
class ModelStats:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0


class CostTracker:
    def __init__(self, budget_usd: float | None = None) -> None:
        self.budget_usd = budget_usd
        self._by_model: dict[str, ModelStats] = {}

    # ------------------------------------------------------------ recording

    def record(self, response: LLMResponse) -> float:
        model = response.model or "unknown"
        usage = response.usage
        cost = cost_usd(model, usage.prompt_tokens, usage.completion_tokens)

        stats = self._by_model.setdefault(model, ModelStats())
        stats.calls += 1
        stats.prompt_tokens += usage.prompt_tokens
        stats.completion_tokens += usage.completion_tokens
        stats.cost += cost

        # Record first, then complain. The spend already happened.
        if self.budget_usd is not None and self.total_cost > self.budget_usd:
            raise BudgetExceeded(self.total_cost, self.budget_usd)
        return cost

    # ------------------------------------------------------------ totals

    @property
    def total_cost(self) -> float:
        return sum(s.cost for s in self._by_model.values())

    @property
    def call_count(self) -> int:
        return sum(s.calls for s in self._by_model.values())

    @property
    def total_prompt_tokens(self) -> int:
        return sum(s.prompt_tokens for s in self._by_model.values())

    @property
    def total_completion_tokens(self) -> int:
        return sum(s.completion_tokens for s in self._by_model.values())

    @property
    def by_model(self) -> dict[str, ModelStats]:
        return dict(self._by_model)

    @property
    def remaining_budget(self) -> float | None:
        if self.budget_usd is None:
            return None
        return self.budget_usd - self.total_cost

    # ------------------------------------------------------------ output

    def report(self) -> str:
        lines = [
            f"{self.call_count} calls  |  {self.total_prompt_tokens:,} in  |  "
            f"{self.total_completion_tokens:,} out  |  ${self.total_cost:.4f}"
        ]
        for model, s in sorted(self._by_model.items(), key=lambda kv: -kv[1].cost):
            lines.append(
                f"  {model:<40} {s.calls:>3} calls  "
                f"{s.prompt_tokens:>8,} in  {s.completion_tokens:>7,} out  "
                f"${s.cost:.4f}"
            )
        if self.budget_usd is not None:
            lines.append(
                f"  budget ${self.budget_usd:.4f}  |  remaining "
                f"${self.remaining_budget:.4f}"
            )
        return "\n".join(lines)

    def reset(self) -> None:
        self._by_model.clear()
