"""Tests for Chapter 4, Exercise 1 — budget and prompt assembly."""

import pytest

from agentlib.tokens import estimate_tokens
from chapters.ch04_context.exercises.exercise_1_budget import ContextBudget, PromptBuilder


class TestContextBudget:
    def test_fixed(self):
        b = ContextBudget(context_window=1000, reserve_output=100,
                          system_tokens=50, tools_tokens=25)
        assert b.fixed == 175

    def test_available(self):
        b = ContextBudget(context_window=1000, reserve_output=100,
                          system_tokens=50, tools_tokens=25)
        assert b.available_for_history == 825

    def test_available_can_be_negative(self):
        # more tools than window. Clamping to 0 hides a broken configuration.
        b = ContextBudget(context_window=100, reserve_output=100, tools_tokens=500)
        assert b.available_for_history < 0

    def test_fits(self):
        b = ContextBudget(context_window=1000, reserve_output=0)
        assert b.fits([{"role": "user", "content": "hi"}])
        assert not b.fits([{"role": "user", "content": "x" * 10_000}])

    def test_headroom(self):
        b = ContextBudget(context_window=100, reserve_output=0)
        msgs = [{"role": "user", "content": "abcd"}]  # 1 + 4 + 3 = 8
        assert b.headroom(msgs) == 92

    def test_headroom_negative_when_over(self):
        b = ContextBudget(context_window=10, reserve_output=0)
        assert b.headroom([{"role": "user", "content": "x" * 400}]) < 0

    def test_output_reserve_is_subtracted(self):
        small = ContextBudget(context_window=1000, reserve_output=900)
        large = ContextBudget(context_window=1000, reserve_output=10)
        assert small.available_for_history < large.available_for_history


class TestMeasure:
    def test_measures_the_system_prompt(self):
        b = ContextBudget.measure(context_window=1000, system="x" * 400)
        assert b.system_tokens == 100

    def test_no_system_prompt(self):
        assert ContextBudget.measure().system_tokens == 0

    def test_measures_tool_specs(self):
        specs = [{"type": "function", "function": {"name": "a", "parameters": {}}}]
        b = ContextBudget.measure(tool_specs=specs)
        assert b.tools_tokens > 0

    def test_no_tools(self):
        assert ContextBudget.measure().tools_tokens == 0

    def test_more_tools_cost_more(self):
        one = ContextBudget.measure(tool_specs=[{"function": {"name": "a"}}])
        ten = ContextBudget.measure(tool_specs=[{"function": {"name": "a"}}] * 10)
        assert ten.tools_tokens > one.tools_tokens


class TestPromptBuilder:
    def test_empty(self):
        assert PromptBuilder().render() == ""

    def test_joins_with_separator(self):
        p = PromptBuilder().add("a", "first").add("b", "second")
        assert p.render() == "first\n\nsecond"

    def test_chaining(self):
        p = PromptBuilder()
        assert p.add("a", "x") is p

    def test_orders_by_priority(self):
        p = (PromptBuilder()
             .add("last", "C", priority=90)
             .add("first", "A", priority=0)
             .add("middle", "B", priority=50))
        assert p.render() == "A\n\nB\n\nC"
        assert p.names == ["first", "middle", "last"]

    def test_equal_priorities_keep_insertion_order(self):
        p = PromptBuilder().add("a", "A", priority=5).add("b", "B", priority=5)
        assert p.names == ["a", "b"]

    def test_skips_empty_content(self):
        p = PromptBuilder().add("a", "A").add("empty", "").add("blank", "   ")
        assert p.names == ["a"]
        assert p.render() == "A"

    def test_strips_content(self):
        assert PromptBuilder().add("a", "  padded  ").render() == "padded"

    def test_drops_least_important_when_over_budget(self):
        p = (PromptBuilder()
             .add("rules", "RULES", priority=0)
             .add("memories", "M" * 4000, priority=90))
        out = p.render(max_tokens=20)
        assert "RULES" in out
        assert "MMMM" not in out

    def test_drops_in_priority_order(self):
        p = (PromptBuilder()
             .add("keep", "K" * 20, priority=0)
             .add("mid", "M" * 200, priority=50)
             .add("drop", "D" * 200, priority=90))
        out = p.render(max_tokens=60)
        assert "K" * 20 in out
        assert "D" * 200 not in out

    def test_required_sections_survive_even_when_over(self):
        p = PromptBuilder().add("rules", "R" * 4000, priority=0, required=True)
        out = p.render(max_tokens=5)
        assert "R" * 4000 in out, "better a clear API error than silently dropping rules"

    def test_no_max_tokens_keeps_everything(self):
        p = PromptBuilder().add("a", "A" * 4000, priority=99)
        assert "A" * 4000 in p.render()
