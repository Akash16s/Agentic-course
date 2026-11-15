"""Tests for Exercise 4 — cost tracking."""

import pytest

from agentlib.errors import BudgetExceeded
from agentlib.llm import LLMResponse, Usage
from chapters.ch01_agent_loop.exercises.exercise_4_cost import CostTracker

MINI = "openai/gpt-4o-mini"          # $0.15 in / $0.60 out per million
SONNET = "anthropic/claude-sonnet-4.5"  # $3.00 in / $15.00 out per million


def resp(model=MINI, pin=1000, pout=500):
    return LLMResponse(text="x", usage=Usage(pin, pout), model=model)


class TestRecording:
    def test_starts_empty(self):
        t = CostTracker()
        assert t.total_cost == 0.0
        assert t.call_count == 0
        assert t.total_prompt_tokens == 0
        assert t.total_completion_tokens == 0

    def test_record_returns_this_calls_cost(self):
        t = CostTracker()
        cost = t.record(resp(MINI, 1_000_000, 1_000_000))
        assert cost == pytest.approx(0.15 + 0.60)

    def test_input_and_output_are_priced_differently(self):
        t = CostTracker()
        in_only = t.record(resp(MINI, 1_000_000, 0))
        out_only = t.record(resp(MINI, 0, 1_000_000))
        assert out_only == pytest.approx(in_only * 4), "output costs ~4x input here"

    def test_accumulates(self):
        t = CostTracker()
        a = t.record(resp())
        b = t.record(resp())
        assert t.call_count == 2
        assert t.total_cost == pytest.approx(a + b)
        assert t.total_prompt_tokens == 2000
        assert t.total_completion_tokens == 1000

    def test_unknown_model_is_not_free(self):
        # Silent zeros hide real money. An unknown model must look expensive.
        t = CostTracker()
        assert t.record(resp("some/brand-new-model", 1_000_000, 0)) > 0


class TestByModel:
    def test_splits_by_model(self):
        t = CostTracker()
        t.record(resp(MINI))
        t.record(resp(MINI))
        t.record(resp(SONNET))
        stats = t.by_model
        assert set(stats) == {MINI, SONNET}
        assert stats[MINI].calls == 2
        assert stats[SONNET].calls == 1
        assert stats[SONNET].cost > stats[MINI].cost

    def test_by_model_totals_match_grand_total(self):
        t = CostTracker()
        t.record(resp(MINI))
        t.record(resp(SONNET))
        assert sum(s.cost for s in t.by_model.values()) == pytest.approx(t.total_cost)

    def test_by_model_is_a_copy(self):
        t = CostTracker()
        t.record(resp(MINI))
        t.by_model.clear()
        assert len(t.by_model) == 1


class TestBudget:
    def test_no_budget_means_no_limit(self):
        t = CostTracker()
        for _ in range(100):
            t.record(resp(SONNET, 1_000_000, 1_000_000))
        assert t.remaining_budget is None

    def test_remaining_budget_decreases(self):
        t = CostTracker(budget_usd=1.0)
        t.record(resp(MINI, 1_000_000, 0))  # $0.15
        assert t.remaining_budget == pytest.approx(0.85)

    def test_raises_when_budget_crossed(self):
        t = CostTracker(budget_usd=0.10)
        with pytest.raises(BudgetExceeded):
            t.record(resp(MINI, 1_000_000, 0))  # $0.15 > $0.10

    def test_the_spend_is_still_recorded_when_it_raises(self):
        # The money left your account. Hiding it from the report helps nobody.
        t = CostTracker(budget_usd=0.10)
        with pytest.raises(BudgetExceeded):
            t.record(resp(MINI, 1_000_000, 0))
        assert t.total_cost == pytest.approx(0.15)
        assert t.call_count == 1

    def test_stays_quiet_below_the_budget(self):
        t = CostTracker(budget_usd=1.0)
        t.record(resp(MINI, 1000, 500))  # fractions of a cent
        assert t.total_cost < 1.0

    def test_exception_carries_the_numbers(self):
        t = CostTracker(budget_usd=0.10)
        with pytest.raises(BudgetExceeded) as exc:
            t.record(resp(MINI, 1_000_000, 0))
        assert exc.value.budget == 0.10
        assert exc.value.spent == pytest.approx(0.15)


class TestOutput:
    def test_report_mentions_models_and_total(self):
        t = CostTracker()
        t.record(resp(MINI))
        t.record(resp(SONNET))
        text = t.report()
        assert MINI in text
        assert SONNET in text
        assert "2" in text  # the call count appears somewhere

    def test_reset(self):
        t = CostTracker(budget_usd=1.0)
        t.record(resp())
        t.reset()
        assert t.total_cost == 0.0
        assert t.call_count == 0
        assert t.by_model == {}
        assert t.remaining_budget == 1.0, "reset clears spend, not the budget"
