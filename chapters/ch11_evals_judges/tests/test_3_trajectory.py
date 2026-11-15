"""Tests for Chapter 11, Exercise 3 — trajectory evaluation."""

import pytest

from agentlib.evals.core import EvalCase
from chapters.ch11_evals_judges.exercises.exercise_3_trajectory import (
    is_subsequence,
    levenshtein,
    tools_of,
    trajectory_contains,
    trajectory_exact,
    trajectory_similarity,
)

CASE = EvalCase(id="1", input="q")


class Result:
    def __init__(self, *tools):
        self.tool_sequence = list(tools)
        self.output = "answer"


class TestToolsOf:
    def test_agent_result(self):
        assert tools_of(Result("a", "b")) == ["a", "b"]

    def test_plain_string(self):
        assert tools_of("just text") == []

    def test_empty(self):
        assert tools_of(Result()) == []


class TestIsSubsequence:
    def test_contiguous(self):
        assert is_subsequence(["a", "b"], ["a", "b", "c"])

    def test_with_gaps(self):
        assert is_subsequence(["a", "c"], ["a", "b", "c"])

    def test_order_matters(self):
        assert not is_subsequence(["c", "a"], ["a", "b", "c"])

    def test_missing_element(self):
        assert not is_subsequence(["a", "z"], ["a", "b", "c"])

    def test_empty_needle(self):
        assert is_subsequence([], ["a"])

    def test_empty_haystack(self):
        assert not is_subsequence(["a"], [])

    def test_repeats_need_enough_occurrences(self):
        assert is_subsequence(["a", "a"], ["a", "b", "a"])
        assert not is_subsequence(["a", "a"], ["a", "b"])


class TestLevenshtein:
    def test_identical(self):
        assert levenshtein(["a", "b"], ["a", "b"]) == 0

    def test_substitution(self):
        assert levenshtein(["a", "b", "c"], ["a", "x", "c"]) == 1

    def test_insertion(self):
        assert levenshtein(["a", "c"], ["a", "b", "c"]) == 1

    def test_deletion(self):
        assert levenshtein(["a", "b", "c"], ["a", "c"]) == 1

    def test_empty_both(self):
        assert levenshtein([], []) == 0

    def test_empty_one(self):
        assert levenshtein([], ["a", "b"]) == 2
        assert levenshtein(["a", "b"], []) == 2

    def test_completely_different(self):
        assert levenshtein(["a", "b"], ["x", "y"]) == 2

    def test_symmetric(self):
        a, b = ["search", "read", "write"], ["read", "search"]
        assert levenshtein(a, b) == levenshtein(b, a)


class TestTrajectoryExact:
    def test_match(self):
        assert trajectory_exact(["a", "b"])(Result("a", "b"), CASE).passed

    def test_extra_tool_fails(self):
        assert not trajectory_exact(["a", "b"])(Result("a", "x", "b"), CASE).passed

    def test_wrong_order_fails(self):
        assert not trajectory_exact(["a", "b"])(Result("b", "a"), CASE).passed

    def test_detail_shows_both_sequences(self):
        detail = trajectory_exact(["a"])(Result("b"), CASE).detail
        assert "a" in detail and "b" in detail

    def test_name(self):
        assert trajectory_exact([])(Result(), CASE).name == "trajectory_exact"


class TestTrajectoryContains:
    def test_exact_match(self):
        assert trajectory_contains(["a", "b"])(Result("a", "b"), CASE).passed

    def test_tolerates_extra_tools(self):
        # the default check: "it looked something up before answering" is what
        # matters, not whether it also listed a directory first
        result = Result("list", "a", "think", "b", "cleanup")
        assert trajectory_contains(["a", "b"])(result, CASE).passed

    def test_order_still_matters(self):
        assert not trajectory_contains(["a", "b"])(Result("b", "a"), CASE).passed

    def test_missing_tool_fails(self):
        assert not trajectory_contains(["a", "b"])(Result("a", "c"), CASE).passed

    def test_empty_expectation_always_passes(self):
        assert trajectory_contains([])(Result("anything"), CASE).passed

    def test_plain_string_output_fails(self):
        assert not trajectory_contains(["a"])("just text", CASE).passed


class TestTrajectorySimilarity:
    def test_identical_scores_one(self):
        result = trajectory_similarity(["a", "b"])(Result("a", "b"), CASE)
        assert result.score == 1.0
        assert result.passed

    def test_one_off_scores_high(self):
        result = trajectory_similarity(["a", "b", "c"])(Result("a", "x", "c"), CASE)
        assert 0.6 < result.score < 1.0
        assert not result.passed

    def test_completely_different_scores_zero(self):
        result = trajectory_similarity(["a", "b"])(Result("x", "y"), CASE)
        assert result.score == 0.0

    def test_grades_rather_than_gates(self):
        # the point: "one tool off" and "a different plan" are different failures
        close = trajectory_similarity(["a", "b", "c"])(Result("a", "b", "x"), CASE)
        far = trajectory_similarity(["a", "b", "c"])(Result("x", "y", "z"), CASE)
        assert close.score > far.score

    def test_empty_expectation_and_output(self):
        assert trajectory_similarity([])(Result(), CASE).score == 1.0

    def test_name(self):
        assert trajectory_similarity([])(Result(), CASE).name == "trajectory_similarity"
