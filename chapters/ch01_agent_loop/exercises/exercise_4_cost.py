"""EXERCISE 4 — Cost tracking and a spend guard.

WHY: An agent is a loop, and a loop can run away. The difference between a $2 bug and a
$2,000 bug is whether anyone was counting. Every production agent I have seen that
survived contact with reality had a cost tracker wired in from day one, and every one
that produced a horror story did not.

You will use this object in every remaining chapter, and Chapter 12 turns it into real
observability.

Run the tests:
    pytest chapters/ch01_agent_loop/tests -q -k cost
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentlib.errors import BudgetExceeded
from agentlib.llm import LLMResponse
from agentlib.pricing import cost_usd


@dataclass
class ModelStats:
    """Per-model totals, so you can see WHERE the money went, not just that it went."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0


class CostTracker:
    """Accumulates spend across many calls.

    >>> t = CostTracker()
    >>> r = LLMResponse(text="hi", usage=Usage(1000, 500), model="openai/gpt-4o-mini")
    >>> round(t.record(r), 6)
    0.00045
    >>> t.call_count
    1
    """

    def __init__(self, budget_usd: float | None = None) -> None:
        """`budget_usd=None` means no limit (but still track everything).

        Suggested internals:
            self.budget_usd: float | None
            self._by_model: dict[str, ModelStats]
        """
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ recording

    def record(self, response: LLMResponse) -> float:
        """Add one response to the totals and return THIS call's cost in dollars.

        Spec:
          * cost comes from `cost_usd(response.model, prompt_tokens, completion_tokens)`
          * update the per-model stats for `response.model`
          * if a budget is set and the new total exceeds it, raise `BudgetExceeded`
            AFTER recording (the money was already spent — hiding it helps nobody)

        Design note: we raise on the call that *crosses* the line, not before it. You
        cannot know a call's cost until it returns. A pre-flight estimate-based guard is
        a different, more conservative tool — you build that in Chapter 13.
        """
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ totals

    @property
    def total_cost(self) -> float:
        # TODO: implement
        raise NotImplementedError

    @property
    def call_count(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def total_prompt_tokens(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def total_completion_tokens(self) -> int:
        # TODO: implement
        raise NotImplementedError

    @property
    def by_model(self) -> dict[str, ModelStats]:
        """Per-model breakdown. Return a copy of the mapping."""
        # TODO: implement
        raise NotImplementedError

    @property
    def remaining_budget(self) -> float | None:
        """budget - spent, or None if there is no budget. May go negative."""
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ output

    def report(self) -> str:
        """A short human-readable summary. Exact format is up to you — the test only
        checks that the model names and the total appear in it.

        Something like:

            3 calls  |  4,500 in  |  1,200 out  |  $0.0231
              openai/gpt-4o-mini        2 calls  $0.0012
              anthropic/claude-sonnet-4.5  1 call  $0.0219
        """
        # TODO: implement
        raise NotImplementedError

    def reset(self) -> None:
        """Clear all totals. Useful between eval runs (Chapter 10)."""
        # TODO: implement
        raise NotImplementedError
