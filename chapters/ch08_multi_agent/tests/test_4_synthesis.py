"""Tests for Chapter 8, Exercise 4 — handoffs and synthesis."""

import pytest

from chapters.ch08_multi_agent.exercises.exercise_3_orchestrator import WorkerResult
from chapters.ch08_multi_agent.exercises.exercise_4_synthesis import (
    Handoff,
    synthesis_prompt,
)


class TestHandoff:
    def test_defaults(self):
        h = Handoff(target="billing")
        assert h.reason == ""
        assert h.context == ""

    def test_describe(self):
        assert Handoff(target="billing", reason="invoice question").describe() == (
            "-> billing: invoice question"
        )

    def test_describe_without_a_reason(self):
        assert Handoff(target="billing").describe() == "-> billing"

    def test_carries_context(self):
        h = Handoff(
            target="billing",
            reason="disputing an invoice",
            context="Akash, account 4471, invoice INV-2201 for $340",
        )
        assert "INV-2201" in h.context


class TestSynthesisPrompt:
    def results(self):
        return [
            WorkerResult(name="pricing", task="research pricing",
                         output="Competitors charge $20-50/month."),
            WorkerResult(name="features", task="research features",
                         output="All three have an API."),
            WorkerResult(name="reviews", task="research reviews",
                         error="RateLimitError: 429"),
        ]

    def test_includes_the_goal(self):
        assert "compare competitors" in synthesis_prompt("compare competitors",
                                                         self.results())

    def test_includes_every_worker_name(self):
        out = synthesis_prompt("goal", self.results())
        for name in ("pricing", "features", "reviews"):
            assert name in out

    def test_includes_successful_output(self):
        out = synthesis_prompt("goal", self.results())
        assert "$20-50/month" in out
        assert "have an API" in out

    def test_failures_are_visible_and_labelled(self):
        # THE test for this function. A synthesiser that cannot see the failure will
        # write a confident paragraph about reviews anyway.
        out = synthesis_prompt("goal", self.results())
        assert "FAILED" in out
        assert "RateLimitError" in out

    def test_instructs_the_model_to_flag_gaps(self):
        out = synthesis_prompt("goal", self.results()).lower()
        assert "missing" in out or "guess" in out

    def test_no_results(self):
        out = synthesis_prompt("goal", [])
        assert "goal" in out

    def test_all_failed(self):
        results = [WorkerResult(name="a", task="t", error="boom")]
        out = synthesis_prompt("goal", results)
        assert "FAILED" in out
