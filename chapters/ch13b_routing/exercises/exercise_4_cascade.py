"""EXERCISE 4 — Cascades: try cheap, check, escalate.

    pytest chapters/ch13b_routing/tests -q -k cascade
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agentlib import errors
from agentlib.llm import LLMResponse, Message
from agentlib.pricing import cost_usd


@dataclass
class CascadeStep:
    """(Given.) One tier's turn."""

    model: str
    output: str = ""
    accepted: bool = False
    cost: float = 0.0
    error: str | None = None       # repr of a retryable error, if the call failed


@dataclass
class CascadeResult:
    """(Given.) What the cascade returns."""

    output: str
    model: str                       # tier whose output we are returning
    accepted: bool                   # False: even the last tier failed the check
    steps: list[CascadeStep] = field(default_factory=list)
    total_cost: float = 0.0

    @property
    def escalations(self) -> int:
        return max(len(self.steps) - 1, 0)


def response_cost(name: str, response: LLMResponse) -> float:
    """(Given.) Default cost function: price response.model, or the tier name if
    the response has no model."""
    u = response.usage
    return cost_usd(response.model or name, u.prompt_tokens, u.completion_tokens)


class Cascade:
    """Try cheap first; CHECK the answer; escalate only if the check fails.

        cascade = Cascade(
            [("nano", LLMClient("openai/gpt-5-nano")),
             ("sonnet", LLMClient("anthropic/claude-sonnet-4.5"))],
            accept=lambda text: is_valid_json(text),
        )
        result = cascade.run(messages)

    __init__(self, tiers: list[tuple[name, client]], accept: Callable[[str], bool],
             *, cost_fn: Callable[[name, LLMResponse], float] = response_cost)
      empty tiers -> ValueError

    `accept` must be something you can VERIFY: a schema check, a test run, a
    judge. Asking the model "how confident are you?" measures confidence, and
    small models are most confident precisely when they are wrong.
    """

    def __init__(
        self,
        tiers: list[tuple[str, Any]],
        accept: Callable[[str], bool],
        *,
        cost_fn: Callable[[str, LLMResponse], float] = response_cost,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def run(self, messages: list[Message], **kwargs: Any) -> CascadeResult:
        """Spec:

          for each (name, client) in order:
            1. response = client.chat(messages, **kwargs)
               - errors.LLMError, NOT retryable -> re-raise (your bug, see ex. 1)
               - errors.LLMError, retryable     -> record
                 CascadeStep(name, error=repr(exc)) and move on. A cascade gets
                 fallback behaviour for free.
            2. step = CascadeStep(name, output=response.text,
                                  cost=self.cost_fn(name, response))
            3. accepted =
                 False                if response.truncated  (cut off = not an answer)
                 False                if self.accept(text) RAISES anything
                                      (json.loads on garbage is a rejection,
                                       not a crash)
                 bool(accept(text))   otherwise
            4. accepted -> stop.

          Return CascadeResult with:
            output/model/accepted from the LAST tier that produced output (so if
            nothing was accepted you still get the strongest model's answer,
            flagged accepted=False — the caller decides what to do with it)
            steps       = every step, errors included
            total_cost  = sum of every step's cost. YOU PAID FOR THE REJECTED
                          ANSWERS TOO; that is the whole maths of section 6.

          No tier produced any output at all (every call errored) -> re-raise the
          LAST error.
        """
        # TODO: implement
        raise NotImplementedError


def expected_cost(p_accept_cheap: float, cost_cheap: float, cost_strong: float) -> float:
    """Expected cost per request of a 2-tier cascade.

        p * c_cheap  +  (1 - p) * (c_cheap + c_strong)
      = c_cheap + (1 - p) * c_strong

    You ALWAYS pay for the cheap call. p outside [0, 1] -> ValueError.
    """
    # TODO: implement
    raise NotImplementedError


def break_even_accept_rate(cost_cheap: float, cost_strong: float) -> float:
    """The accept rate at which the cascade costs exactly the same as strong-only.

        c_cheap + (1 - p) * c_strong == c_strong   ->   p = c_cheap / c_strong

    Below it the cascade LOSES money. A result above 1.0 means it can never win.
    cost_strong <= 0 -> ValueError.
    """
    # TODO: implement
    raise NotImplementedError


def savings_vs_strong(p_accept_cheap: float, cost_cheap: float,
                      cost_strong: float) -> float:
    """1 - expected_cost(...) / cost_strong. Negative means the cascade loses."""
    # TODO: implement
    raise NotImplementedError


def expected_cost_chain(costs: list[float], accept_rates: list[float]) -> float:
    """Expected cost of an N-tier cascade.

    accept_rates[i] = chance tier i's answer passes, GIVEN the request reached
    tier i. There is one fewer rate than costs: the last tier is final.

        total = c0 + (1-p0)*c1 + (1-p0)*(1-p1)*c2 + ...

    Errors (ValueError): empty costs; len(accept_rates) != len(costs) - 1; any
    rate outside [0, 1]. With two tiers this must equal expected_cost().
    """
    # TODO: implement
    raise NotImplementedError
