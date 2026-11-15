"""SOLUTION — Chapter 13b, Exercise 4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agentlib import errors
from agentlib.llm import LLMResponse, Message
from agentlib.pricing import cost_usd


@dataclass
class CascadeStep:
    model: str
    output: str = ""
    accepted: bool = False
    cost: float = 0.0
    error: str | None = None


@dataclass
class CascadeResult:
    output: str
    model: str
    accepted: bool
    steps: list[CascadeStep] = field(default_factory=list)
    total_cost: float = 0.0

    @property
    def escalations(self) -> int:
        return max(len(self.steps) - 1, 0)


def response_cost(name: str, response: LLMResponse) -> float:
    u = response.usage
    return cost_usd(response.model or name, u.prompt_tokens, u.completion_tokens)


class Cascade:
    def __init__(
        self,
        tiers: list[tuple[str, Any]],
        accept: Callable[[str], bool],
        *,
        cost_fn: Callable[[str, LLMResponse], float] = response_cost,
    ) -> None:
        if not tiers:
            raise ValueError("a cascade needs at least one tier")
        self.tiers = list(tiers)
        self.accept = accept
        self.cost_fn = cost_fn

    def _accepts(self, response: LLMResponse) -> bool:
        if response.truncated:
            return False
        try:
            return bool(self.accept(response.text))
        except Exception:  # noqa: BLE001
            return False

    def run(self, messages: list[Message], **kwargs: Any) -> CascadeResult:
        steps: list[CascadeStep] = []
        last_ok: CascadeStep | None = None
        last_error: errors.LLMError | None = None

        for name, client in self.tiers:
            try:
                response = client.chat(messages, **kwargs)
            except errors.LLMError as exc:
                if not exc.retryable:
                    raise
                steps.append(CascadeStep(model=name, error=repr(exc)))
                last_error = exc
                continue
            step = CascadeStep(model=name, output=response.text,
                               cost=self.cost_fn(name, response))
            step.accepted = self._accepts(response)
            steps.append(step)
            last_ok = step
            if step.accepted:
                break

        if last_ok is None:
            assert last_error is not None
            raise last_error
        return CascadeResult(
            output=last_ok.output,
            model=last_ok.model,
            accepted=last_ok.accepted,
            steps=steps,
            total_cost=sum(s.cost for s in steps),
        )


def expected_cost(p_accept_cheap: float, cost_cheap: float, cost_strong: float) -> float:
    if not 0.0 <= p_accept_cheap <= 1.0:
        raise ValueError("p_accept_cheap must be between 0 and 1")
    return cost_cheap + (1.0 - p_accept_cheap) * cost_strong


def break_even_accept_rate(cost_cheap: float, cost_strong: float) -> float:
    if cost_strong <= 0:
        raise ValueError("cost_strong must be positive")
    return cost_cheap / cost_strong


def savings_vs_strong(p_accept_cheap: float, cost_cheap: float,
                      cost_strong: float) -> float:
    return 1.0 - expected_cost(p_accept_cheap, cost_cheap, cost_strong) / cost_strong


def expected_cost_chain(costs: list[float], accept_rates: list[float]) -> float:
    if not costs:
        raise ValueError("need at least one tier")
    if len(accept_rates) != len(costs) - 1:
        raise ValueError("need exactly len(costs) - 1 accept rates")
    if any(not 0.0 <= p <= 1.0 for p in accept_rates):
        raise ValueError("accept rates must be between 0 and 1")
    total = 0.0
    p_reach = 1.0
    for i, cost in enumerate(costs):
        total += p_reach * cost
        if i < len(accept_rates):
            p_reach *= 1.0 - accept_rates[i]
    return total
