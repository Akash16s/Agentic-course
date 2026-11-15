"""SOLUTION — Chapter 13b, Exercise 2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentlib import errors


@dataclass(frozen=True)
class ModelSpec:
    """What you know about a model before you call it."""

    name: str
    context_window: int          # total tokens: input + output
    price_in: float              # $ per MILLION input tokens
    price_out: float             # $ per MILLION output tokens
    supports_tools: bool = True
    supports_vision: bool = False
    tier: int = 1                # 1 = small/cheap, 2 = mid, 3 = frontier


class NoModelFits(errors.BadRequestError):
    """No configured model can serve this request. Says why, per model."""

    def __init__(self, reasons: dict[str, str]) -> None:
        detail = "; ".join(f"{k}: {v}" for k, v in reasons.items()) or "no models"
        super().__init__(f"no model fits -> {detail}")
        self.reasons = reasons


TASK_MIN_TIER: dict[str, int] = {
    "classify": 1,
    "extract": 1,
    "summarise": 1,
    "chat": 1,
    "code": 2,
    "plan": 2,
    "reason": 3,
}


def estimate_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * spec.price_in + output_tokens * spec.price_out) / 1_000_000


def fits_context(spec: ModelSpec, input_tokens: int, output_tokens: int) -> bool:
    return input_tokens + output_tokens <= spec.context_window


def select_model(
    specs: list[ModelSpec],
    *,
    input_tokens: int,
    output_tokens: int = 1024,
    needs_tools: bool = False,
    needs_vision: bool = False,
    min_tier: int = 1,
    max_tier: int | None = None,
) -> ModelSpec:
    reasons: dict[str, str] = {}
    capable: list[ModelSpec] = []
    for spec in specs:
        if needs_tools and not spec.supports_tools:
            reasons[spec.name] = "no tool support"
        elif needs_vision and not spec.supports_vision:
            reasons[spec.name] = "no vision support"
        elif spec.tier < min_tier:
            reasons[spec.name] = f"tier {spec.tier} below min_tier {min_tier}"
        elif max_tier is not None and spec.tier > max_tier:
            reasons[spec.name] = f"tier {spec.tier} above max_tier {max_tier}"
        elif not fits_context(spec, input_tokens, output_tokens):
            reasons[spec.name] = (
                f"context {spec.context_window:,} < "
                f"{input_tokens:,} in + {output_tokens:,} out")
        else:
            capable.append(spec)
    if not capable:
        raise NoModelFits(reasons)
    return min(capable,
               key=lambda s: (estimate_cost(s, input_tokens, output_tokens), s.tier))


def select_for_task(specs: list[ModelSpec], task: str, **kwargs: Any) -> ModelSpec:
    return select_model(specs, min_tier=TASK_MIN_TIER.get(task, 1), **kwargs)
