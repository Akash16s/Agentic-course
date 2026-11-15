"""EXERCISE 2 — Static routing: which models CAN serve this request?

    pytest chapters/ch13b_routing/tests -q -k rules
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentlib import errors


@dataclass(frozen=True)
class ModelSpec:
    """What you know about a model before you call it. (Given.)

    Fill these in from OpenRouter's /models endpoint (Chapter 1's
    00_check_setup.py prints it), not from memory — prices and context windows
    change, and model ids disappear.
    """

    name: str
    context_window: int          # total tokens: input + output
    price_in: float              # $ per MILLION input tokens
    price_out: float             # $ per MILLION output tokens
    supports_tools: bool = True
    supports_vision: bool = False
    tier: int = 1                # 1 = small/cheap, 2 = mid, 3 = frontier


class NoModelFits(errors.BadRequestError):
    """No configured model can serve this request. Says why, per model. (Given.)

    A BadRequestError on purpose: no amount of retrying or falling back fixes a
    request that is too long for every model you have. Exercise 1's
    FallbackClient will (correctly) refuse to fall back on it.
    """

    def __init__(self, reasons: dict[str, str]) -> None:
        detail = "; ".join(f"{k}: {v}" for k, v in reasons.items()) or "no models"
        super().__init__(f"no model fits -> {detail}")
        self.reasons = reasons


#: Static routing by task type: the lowest tier each kind of task may use. (Given.)
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
    """Dollar cost of one call on `spec`.

    Prices are per MILLION tokens, input and output billed separately:
        (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    """
    # TODO: implement
    raise NotImplementedError


def fits_context(spec: ModelSpec, input_tokens: int, output_tokens: int) -> bool:
    """True if input + output <= context_window. Exactly equal fits.

    The output counts. A 128k window with 127.9k of input "fits" until the
    model has 100 tokens left to answer in and stops mid-sentence with
    finish_reason == "length".
    """
    # TODO: implement
    raise NotImplementedError


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
    """The CHEAPEST model that CAN serve this request.

    Spec:
      1. Walk `specs` in order. Reject a spec, recording ONE reason string under
         reasons[spec.name], checking in this order (first failure wins):
            needs_tools and not supports_tools   -> reason containing "tool"
            needs_vision and not supports_vision -> reason containing "vision"
            tier < min_tier                       -> reason containing "tier"
            max_tier set and tier > max_tier      -> reason containing "tier"
            not fits_context(...)                 -> reason containing "context"
      2. Nothing left -> raise NoModelFits(reasons). Empty specs too.
      3. Otherwise return the capable spec with the lowest
         estimate_cost(spec, input_tokens, output_tokens). Ties: lower tier
         wins; a full tie, the one listed first.
         (Hint: min() with a tuple key is stable.)

    "Cheapest" depends on the request. A model with cheap input and dear output
    wins long-document summaries and loses long-form generation. That is why
    this takes token counts rather than sorting the list once at startup.

    Never mutate `specs`.
    """
    # TODO: implement
    raise NotImplementedError


def select_for_task(specs: list[ModelSpec], task: str, **kwargs: Any) -> ModelSpec:
    """select_model with min_tier = TASK_MIN_TIER.get(task, 1).

    All other keyword arguments pass straight through. Unknown task types get
    tier 1: the rules are a FLOOR you add on purpose, not a guess.
    """
    # TODO: implement
    raise NotImplementedError
