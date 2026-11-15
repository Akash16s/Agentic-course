"""Tests for Chapter 13b, Exercise 2 — static routing rules."""

import pytest

from agentlib import errors
from chapters.ch13b_routing.exercises.exercise_2_rules import (
    ModelSpec,
    NoModelFits,
    estimate_cost,
    fits_context,
    select_for_task,
    select_model,
)

NANO = ModelSpec("nano", context_window=128_000, price_in=0.05, price_out=0.40,
                 supports_tools=True, supports_vision=False, tier=1)
SMALL_CTX = ModelSpec("small-ctx", context_window=8_000, price_in=0.02, price_out=0.10,
                      supports_tools=False, supports_vision=False, tier=1)
MID = ModelSpec("mid", context_window=200_000, price_in=1.00, price_out=5.00,
                supports_tools=True, supports_vision=True, tier=2)
FRONTIER = ModelSpec("frontier", context_window=1_000_000, price_in=3.00,
                     price_out=15.00, supports_tools=True, supports_vision=True, tier=3)
ALL = [FRONTIER, MID, NANO, SMALL_CTX]      # deliberately not sorted by price


class TestEstimateCost:
    def test_per_million_pricing(self):
        assert estimate_cost(MID, 1_000_000, 0) == pytest.approx(1.00)
        assert estimate_cost(MID, 0, 1_000_000) == pytest.approx(5.00)

    def test_input_and_output_add_up(self):
        # 2,000 in at $3/M + 500 out at $15/M = 0.006 + 0.0075
        assert estimate_cost(FRONTIER, 2_000, 500) == pytest.approx(0.0135)

class TestFitsContext:
    def test_exactly_full_fits(self):
        assert fits_context(SMALL_CTX, 7_000, 1_000)

    def test_one_over_does_not_fit(self):
        assert not fits_context(SMALL_CTX, 7_001, 1_000)

    def test_output_needs_room_too(self):
        # the input alone fits; the input plus the answer does not
        assert not fits_context(SMALL_CTX, 7_500, 1_000)


class TestSelectModel:
    def test_picks_the_cheapest_capable_model(self):
        assert select_model(ALL, input_tokens=1_000).name == "small-ctx"

    def test_tools_filter(self):
        assert select_model(ALL, input_tokens=1_000, needs_tools=True).name == "nano"

    def test_vision_filter(self):
        assert select_model(ALL, input_tokens=1_000, needs_vision=True).name == "mid"

    def test_long_input_skips_small_context(self):
        assert select_model(ALL, input_tokens=50_000).name == "nano"

    def test_output_headroom_counts(self):
        # 7,500 in fits SMALL_CTX alone, but not with 1,024 out
        assert select_model(ALL, input_tokens=7_500).name == "nano"
        assert select_model(ALL, input_tokens=7_500, output_tokens=200).name == "small-ctx"

    def test_min_tier_floor(self):
        assert select_model(ALL, input_tokens=1_000, min_tier=2).name == "mid"

    def test_max_tier_cap(self):
        with pytest.raises(NoModelFits):
            select_model(ALL, input_tokens=500_000, max_tier=2)

    def test_cheapest_depends_on_the_token_mix(self):
        reader = ModelSpec("reader", 200_000, price_in=0.10, price_out=4.00)
        writer = ModelSpec("writer", 200_000, price_in=1.00, price_out=0.50)
        # summarise a long document: lots in, little out
        assert select_model([reader, writer], input_tokens=100_000,
                            output_tokens=200).name == "reader"
        # write a long report from a short prompt
        assert select_model([reader, writer], input_tokens=200,
                            output_tokens=8_000).name == "writer"

    def test_price_tie_goes_to_the_lower_tier(self):
        a = ModelSpec("a", 100_000, 1.0, 1.0, tier=2)
        b = ModelSpec("b", 100_000, 1.0, 1.0, tier=1)
        assert select_model([a, b], input_tokens=10).name == "b"

    def test_full_tie_goes_to_the_first_listed(self):
        a = ModelSpec("a", 100_000, 1.0, 1.0, tier=1)
        b = ModelSpec("b", 100_000, 1.0, 1.0, tier=1)
        assert select_model([a, b], input_tokens=10).name == "a"
        assert select_model([b, a], input_tokens=10).name == "b"


class TestNoModelFits:
    def test_raised_when_nothing_fits(self):
        with pytest.raises(NoModelFits):
            select_model(ALL, input_tokens=2_000_000)

    def test_empty_specs(self):
        with pytest.raises(NoModelFits):
            select_model([], input_tokens=10)

    def test_is_a_non_retryable_bad_request(self):
        # so a FallbackClient will (correctly) refuse to fall back on it
        with pytest.raises(errors.BadRequestError) as exc:
            select_model([SMALL_CTX], input_tokens=100_000)
        assert exc.value.retryable is False

    def test_says_why_for_every_model(self):
        with pytest.raises(NoModelFits) as exc:
            select_model(ALL, input_tokens=600_000, needs_vision=True, max_tier=2)
        reasons = exc.value.reasons
        assert set(reasons) == {"frontier", "mid", "nano", "small-ctx"}
        assert "tier" in reasons["frontier"]
        assert "context" in reasons["mid"]
        assert "vision" in reasons["nano"]

class TestSelectForTask:
    def test_simple_task_gets_the_cheapest(self):
        assert select_for_task(ALL, "classify", input_tokens=500).name == "small-ctx"

    def test_code_task_has_a_tier_floor(self):
        assert select_for_task(ALL, "code", input_tokens=500).name == "mid"

    def test_reasoning_task_goes_to_frontier(self):
        assert select_for_task(ALL, "reason", input_tokens=500).name == "frontier"

    def test_unknown_task_has_no_floor(self):
        assert select_for_task(ALL, "haiku-writing", input_tokens=500).name == "small-ctx"

    def test_other_constraints_still_apply(self):
        assert select_for_task(ALL, "classify", input_tokens=500,
                               needs_tools=True).name == "nano"
