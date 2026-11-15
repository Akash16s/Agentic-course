"""Tests for Chapter 13b, Exercise 4 — cascades and their maths."""

import json

import pytest

from agentlib import errors
from agentlib.llm import LLMResponse, Usage
from agentlib.pricing import cost_usd
from agentlib.testing import FakeLLMClient
from chapters.ch13b_routing.exercises.exercise_4_cascade import (
    Cascade,
    CascadeResult,
    break_even_accept_rate,
    expected_cost,
    expected_cost_chain,
    savings_vs_strong,
)

MSGS = [{"role": "user", "content": "give me JSON"}]


def flat_cost(prices):
    """A cost_fn that charges a fixed price per tier name."""
    return lambda name, response: prices[name]


def is_json(text):
    json.loads(text)          # raises on garbage — the cascade must treat that as "no"
    return True


def two_tier(cheap_reply, strong_reply="strong answer", accept=lambda t: "ok" in t):
    cheap, strong = FakeLLMClient([cheap_reply]), FakeLLMClient([strong_reply])
    cascade = Cascade([("cheap", cheap), ("strong", strong)], accept,
                      cost_fn=flat_cost({"cheap": 0.001, "strong": 0.02}))
    return cascade, cheap, strong


class TestCascadeRun:
    def test_cheap_answer_accepted_stops_there(self):
        cascade, _, strong = two_tier("ok from cheap")
        result = cascade.run(MSGS)
        assert isinstance(result, CascadeResult)
        assert result.output == "ok from cheap"
        assert result.model == "cheap"
        assert result.accepted is True
        assert strong.call_count == 0

    def test_rejected_cheap_answer_escalates(self):
        cascade, _, strong = two_tier("nope", "ok from strong")
        result = cascade.run(MSGS)
        assert result.output == "ok from strong"
        assert result.model == "strong"
        assert result.accepted is True
        assert strong.call_count == 1

    def test_you_pay_for_the_rejected_answer_too(self):
        cascade, _, _ = two_tier("nope", "ok")
        result = cascade.run(MSGS)
        assert result.total_cost == pytest.approx(0.001 + 0.02)

    def test_steps_record_every_tier_tried(self):
        cascade, _, _ = two_tier("nope", "ok")
        result = cascade.run(MSGS)
        steps = result.steps
        assert result.escalations == 1
        assert [(s.model, s.accepted) for s in steps] == [("cheap", False),
                                                          ("strong", True)]
        assert steps[0].output == "nope"
        assert steps[0].cost == pytest.approx(0.001)

    def test_nothing_accepted_returns_the_last_answer_flagged(self):
        cascade, _, _ = two_tier("nope", "still nope")
        result = cascade.run(MSGS)
        assert result.output == "still nope"
        assert result.model == "strong"
        assert result.accepted is False

    def test_forwards_messages_and_kwargs(self):
        cascade, cheap, strong = two_tier("nope", "ok")
        cascade.run(MSGS, max_tokens=99)
        for client in (cheap, strong):
            assert client.calls[0] == (MSGS, {"max_tokens": 99})

    def test_three_tiers_stop_at_the_first_accept(self):
        a, b, c = FakeLLMClient(["x"]), FakeLLMClient(["ok"]), FakeLLMClient(["ok"])
        result = Cascade([("a", a), ("b", b), ("c", c)], lambda t: t == "ok",
                         cost_fn=flat_cost({"a": 1, "b": 2, "c": 3})).run(MSGS)
        assert result.model == "b"
        assert result.total_cost == 3
        assert c.call_count == 0

    def test_empty_tiers_rejected(self):
        with pytest.raises(ValueError):
            Cascade([], lambda t: True)


class TestAcceptance:
    def test_a_crashing_validator_means_reject_not_crash(self):
        cascade, _, _ = two_tier("not json at all", '{"a": 1}', accept=is_json)
        result = cascade.run(MSGS)
        assert result.model == "strong"
        assert result.output == '{"a": 1}'

    def test_truncated_output_is_rejected(self):
        cut_off = LLMResponse(text="ok but cut", finish_reason="length")
        cascade, _, _ = two_tier(cut_off, "ok full answer")
        result = cascade.run(MSGS)
        assert result.model == "strong"
        assert result.steps[0].accepted is False

class TestErrorsInACascade:
    def test_retryable_error_escalates(self):
        cascade, _, _ = two_tier(errors.RateLimitError("429"), "ok from strong")
        result = cascade.run(MSGS)
        assert result.model == "strong"
        assert result.steps[0].error is not None
        assert result.steps[0].cost == 0

    def test_non_retryable_error_is_raised(self):
        cascade, _, strong = two_tier(errors.BadRequestError("bad"))
        with pytest.raises(errors.BadRequestError):
            cascade.run(MSGS)
        assert strong.call_count == 0

    def test_every_tier_erroring_raises_the_last_error(self):
        last = errors.ServerError("strong down too")
        cascade, _, _ = two_tier(errors.ServerError("cheap down"), last)
        with pytest.raises(errors.ServerError) as exc:
            cascade.run(MSGS)
        assert exc.value is last


class TestDefaultCost:
    def test_prices_the_response_model_from_the_pricing_table(self):
        response = LLMResponse("ok", usage=Usage(1_000, 500), model="openai/gpt-4o")
        result = Cascade([("cheap", FakeLLMClient([response]))],
                         lambda t: True).run(MSGS)
        assert result.total_cost == pytest.approx(cost_usd("openai/gpt-4o", 1_000, 500))


class TestExpectedCost:
    def test_always_accepted_costs_only_cheap(self):
        assert expected_cost(1.0, 0.001, 0.02) == pytest.approx(0.001)

    def test_never_accepted_costs_both(self):
        assert expected_cost(0.0, 0.001, 0.02) == pytest.approx(0.021)

    def test_formula(self):
        # 0.7 * 0.001 + 0.3 * (0.001 + 0.02)
        assert expected_cost(0.7, 0.001, 0.02) == pytest.approx(0.007)

    @pytest.mark.parametrize("p", [-0.1, 1.5])
    def test_probability_must_be_valid(self, p):
        with pytest.raises(ValueError):
            expected_cost(p, 0.001, 0.02)


class TestBreakEven:
    def test_ratio_of_costs(self):
        assert break_even_accept_rate(0.001, 0.02) == pytest.approx(0.05)

    def test_at_break_even_the_cascade_costs_the_same_as_strong(self):
        p = break_even_accept_rate(0.004, 0.02)
        assert expected_cost(p, 0.004, 0.02) == pytest.approx(0.02)

    def test_above_one_means_never(self):
        assert break_even_accept_rate(0.03, 0.02) > 1.0

    def test_strong_cost_must_be_positive(self):
        with pytest.raises(ValueError):
            break_even_accept_rate(0.001, 0)


class TestSavings:
    def test_savings(self):
        # expected 0.007 vs 0.02 -> 65% saved
        assert savings_vs_strong(0.7, 0.001, 0.02) == pytest.approx(0.65)

    def test_a_losing_cascade_has_negative_savings(self):
        assert savings_vs_strong(0.0, 0.001, 0.02) < 0


class TestExpectedCostChain:
    def test_two_tiers_matches_expected_cost(self):
        assert expected_cost_chain([0.001, 0.02], [0.7]) == pytest.approx(
            expected_cost(0.7, 0.001, 0.02))

    def test_three_tiers(self):
        # 1 + 0.5*10 + 0.5*0.2*100
        assert expected_cost_chain([1, 10, 100], [0.5, 0.8]) == pytest.approx(16.0)

    def test_rates_must_be_one_fewer_than_costs(self):
        with pytest.raises(ValueError):
            expected_cost_chain([1, 2], [0.5, 0.5])

    def test_invalid_rate(self):
        with pytest.raises(ValueError):
            expected_cost_chain([1, 2], [1.2])
