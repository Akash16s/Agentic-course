"""Tests for Chapter 10, Exercise 2 — checks."""

import pytest

from chapters.ch10_evals_basics.exercises.exercise_1_dataset import EvalCase
from chapters.ch10_evals_basics.exercises.exercise_2_checks import (
    contains,
    custom,
    equals_expected,
    expected_contains,
    matches,
    max_cost,
    max_steps,
    not_contains,
    succeeded,
    text_of,
    tool_called,
    tool_not_called,
)

CASE = EvalCase(id="1", input="q", expected="Paris")


class FakeResult:
    """Stands in for an AgentResult."""

    def __init__(self, output="", tools=(), steps=0, cost=0.0, ok=True, reason="done"):
        self.output = output
        self.tool_sequence = list(tools)
        self.step_count = steps
        self.cost = cost
        self.succeeded = ok
        self.stop_reason = type("R", (), {"value": reason})()


class TestTextOf:
    def test_string(self):
        assert text_of("hello") == "hello"

    def test_agent_result(self):
        assert text_of(FakeResult(output="hello")) == "hello"

    def test_none_output(self):
        assert text_of(FakeResult(output=None)) == ""


class TestOutputChecks:
    def test_contains(self):
        assert contains("paris")("Paris is nice", CASE).passed
        assert not contains("berlin")("Paris is nice", CASE).passed

    def test_contains_case_sensitive(self):
        assert not contains("paris", case_sensitive=True)("Paris", CASE).passed

    def test_contains_detail_on_failure(self):
        assert "berlin" in contains("berlin")("Paris", CASE).detail

    def test_not_contains(self):
        assert not_contains("sorry")("Here you go", CASE).passed
        assert not not_contains("sorry")("I'm sorry", CASE).passed

    def test_matches(self):
        assert matches(r"\d{4}-\d{2}-\d{2}")("on 2026-09-20", CASE).passed
        assert not matches(r"\d{4}")("no digits", CASE).passed

    def test_matches_searches_anywhere(self):
        assert matches("world")("hello world", CASE).passed

    def test_equals_expected_normalises(self):
        assert equals_expected()("  PARIS \n", CASE).passed, (
            "without normalising, a third of failures are whitespace"
        )

    def test_equals_expected_rejects_different_text(self):
        assert not equals_expected()("Berlin", CASE).passed

    def test_equals_expected_custom_normaliser(self):
        check = equals_expected(normalise=lambda s: s.replace(" ", ""))
        assert check("P a r i s", EvalCase(id="1", input="q", expected="Paris")).passed

    def test_expected_contains_string(self):
        assert expected_contains()("The capital is Paris", CASE).passed

    def test_expected_contains_list(self):
        case = EvalCase(id="1", input="q", expected=["Paris", "France"])
        assert expected_contains()("Paris, France", case).passed
        assert not expected_contains()("Paris only", case).passed

    def test_expected_contains_reports_all_missing(self):
        case = EvalCase(id="1", input="q", expected=["a", "b", "c"])
        detail = expected_contains()("only a", case).detail
        assert "b" in detail and "c" in detail

    def test_check_names(self):
        assert contains("x")("y", CASE).name == "contains"
        assert not_contains("x")("y", CASE).name == "not_contains"
        assert matches("x")("y", CASE).name == "matches"


class TestTrajectoryChecks:
    def test_tool_called(self):
        result = FakeResult(tools=["search", "read"])
        assert tool_called("search")(result, CASE).passed
        assert not tool_called("write")(result, CASE).passed

    def test_tool_called_reports_what_did_happen(self):
        detail = tool_called("search")(FakeResult(tools=["read"]), CASE).detail
        assert "read" in detail

    def test_tool_not_called(self):
        result = FakeResult(tools=["search"])
        assert tool_not_called("delete_user")(result, CASE).passed
        assert not tool_not_called("search")(result, CASE).passed

    def test_trajectory_checks_on_a_plain_string_fail_cleanly(self):
        assert not tool_called("search")("just text", CASE).passed

    def test_max_steps(self):
        assert max_steps(5)(FakeResult(steps=3), CASE).passed
        assert not max_steps(5)(FakeResult(steps=11), CASE).passed

    def test_max_steps_catches_the_right_answer_reached_badly(self):
        result = FakeResult(output="Paris", steps=11, tools=["search"] * 11)
        assert expected_contains()(result, CASE).passed
        assert not max_steps(5)(result, CASE).passed

    def test_max_cost(self):
        assert max_cost(0.05)(FakeResult(cost=0.01), CASE).passed
        assert not max_cost(0.05)(FakeResult(cost=0.9), CASE).passed

    def test_succeeded(self):
        assert succeeded()(FakeResult(ok=True), CASE).passed
        failed = succeeded()(FakeResult(ok=False, reason="max_steps"), CASE)
        assert not failed.passed
        assert "max_steps" in failed.detail


class TestCustom:
    def test_passing(self):
        check = custom("is_short", lambda o, c: len(text_of(o)) < 10)
        assert check("hi", CASE).passed

    def test_failing(self):
        check = custom("is_short", lambda o, c: len(text_of(o)) < 3, detail="too long")
        result = check("far too long", CASE)
        assert not result.passed
        assert result.detail == "too long"

    def test_a_raising_check_is_a_failed_check_not_a_crash(self):
        def explode(output, case):
            raise ValueError("bug in my check")

        result = custom("broken", explode)("x", CASE)
        assert not result.passed
        assert "ValueError" in result.detail

    def test_name_is_preserved(self):
        assert custom("my_check", lambda o, c: True)("x", CASE).name == "my_check"
