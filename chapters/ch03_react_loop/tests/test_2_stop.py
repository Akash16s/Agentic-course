"""Tests for Chapter 3, Exercise 2 — stop conditions."""

import pytest

from agentlib.llm import LLMResponse
from agentlib.tools import ToolCall
from chapters.ch03_react_loop.exercises.exercise_1_result import Step, StopReason
from chapters.ch03_react_loop.exercises.exercise_2_stop import (
    check_stop_conditions,
    detect_repetition,
)


def step(name=None, args=None):
    calls = [ToolCall(id="c", name=name, arguments=args if args is not None else {})] if name else []
    return Step(index=0, response=LLMResponse(text=""), tool_calls=calls)


class TestCheckStopConditions:
    def test_continue_when_nothing_is_hit(self):
        assert check_stop_conditions([], max_steps=5) is None

    def test_max_steps(self):
        assert check_stop_conditions([step()] * 5, max_steps=5) == StopReason.MAX_STEPS

    def test_max_steps_is_inclusive(self):
        # 3 steps taken with max_steps=3 means done. `>` instead of `>=` ships an
        # agent that runs one step more than you configured, every time.
        assert check_stop_conditions([step()] * 3, max_steps=3) == StopReason.MAX_STEPS
        assert check_stop_conditions([step()] * 2, max_steps=3) is None

    def test_zero_max_steps_stops_immediately(self):
        assert check_stop_conditions([], max_steps=0) == StopReason.MAX_STEPS

    def test_budget(self):
        got = check_stop_conditions([], max_steps=10, spent_usd=1.0, budget_usd=1.0)
        assert got == StopReason.BUDGET

    def test_under_budget_continues(self):
        assert check_stop_conditions([], max_steps=10, spent_usd=0.5, budget_usd=1.0) is None

    def test_no_budget_means_no_budget_stop(self):
        assert check_stop_conditions([], max_steps=10, spent_usd=999.0) is None

    def test_timeout(self):
        got = check_stop_conditions([], max_steps=10, elapsed_s=31, timeout_s=30)
        assert got == StopReason.TIMEOUT

    def test_no_timeout_configured(self):
        assert check_stop_conditions([], max_steps=10, elapsed_s=99999) is None

    def test_budget_wins_over_everything(self):
        got = check_stop_conditions(
            [step()] * 99, max_steps=5, elapsed_s=99, timeout_s=1,
            spent_usd=9.0, budget_usd=1.0,
        )
        assert got == StopReason.BUDGET, "money is the limit a human must act on"

    def test_timeout_wins_over_max_steps(self):
        got = check_stop_conditions([step()] * 99, max_steps=5, elapsed_s=99, timeout_s=1)
        assert got == StopReason.TIMEOUT


class TestDetectRepetition:
    def test_too_few_steps(self):
        assert not detect_repetition([step("search", {"q": "x"})] * 2)

    def test_three_identical_calls(self):
        assert detect_repetition([step("search", {"q": "x"})] * 3)

    def test_same_tool_different_arguments_is_fine(self):
        steps = [step("search", {"q": q}) for q in ("a", "b", "c")]
        assert not detect_repetition(steps)

    def test_different_tools(self):
        assert not detect_repetition([step("a"), step("b"), step("c")])

    def test_only_the_last_window_matters(self):
        steps = [step("old", {"q": 1})] + [step("search", {"q": "x"})] * 3
        assert detect_repetition(steps)

    def test_recovery_resets_it(self):
        steps = [step("search", {"q": "x"})] * 3 + [step("read", {"p": "f"})]
        assert not detect_repetition(steps)

    def test_json_string_and_dict_arguments_compare_equal(self):
        steps = [
            step("search", {"q": "x"}),
            step("search", '{"q": "x"}'),
            step("search", {"q": "x"}),
        ]
        assert detect_repetition(steps), "same call, two encodings"

    def test_key_order_does_not_matter(self):
        steps = [
            step("s", {"a": 1, "b": 2}),
            step("s", {"b": 2, "a": 1}),
            step("s", {"a": 1, "b": 2}),
        ]
        assert detect_repetition(steps)

    def test_steps_without_tools_are_not_repetition(self):
        assert not detect_repetition([step(), step(), step()])

    def test_parallel_calls_are_not_repetition(self):
        s = Step(
            index=0,
            response=LLMResponse(text=""),
            tool_calls=[ToolCall(id="1", name="a"), ToolCall(id="2", name="a")],
        )
        assert not detect_repetition([s, s, s])

    def test_custom_window(self):
        assert detect_repetition([step("s", {"q": 1})] * 2, window=2)
