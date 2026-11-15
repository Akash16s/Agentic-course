"""Tests for Chapter 10, Exercise 4 — the runner."""

import time

import pytest

from chapters.ch10_evals_basics.exercises.exercise_1_dataset import Dataset, EvalCase
from chapters.ch10_evals_basics.exercises.exercise_2_checks import (
    CheckResult,
    contains,
    custom,
    expected_contains,
    max_cost,
)
from chapters.ch10_evals_basics.exercises.exercise_4_runner import EvalRunner


def dataset(n=3):
    return Dataset(
        [EvalCase(id=str(i), input=f"q{i}", expected=f"a{i}") for i in range(n)],
        name="test-suite",
    )


def perfect(question):
    return f"the answer is a{question[1:]}"


class FakeResult:
    def __init__(self, output, cost=0.0):
        self.output = output
        self.cost = cost


class TestRunOne:
    def test_passing_case(self):
        runner = EvalRunner(perfect, [expected_contains()])
        result = runner.run_one(EvalCase(id="1", input="q1", expected="a1"))
        assert result.passed
        assert result.output == "the answer is a1"

    def test_failing_case(self):
        runner = EvalRunner(lambda q: "wrong", [expected_contains()])
        result = runner.run_one(EvalCase(id="1", input="q1", expected="a1"))
        assert not result.passed
        assert len(result.failures) == 1

    def test_records_duration(self):
        runner = EvalRunner(lambda q: (time.sleep(0.02), "x")[1], [])
        assert runner.run_one(EvalCase(id="1", input="q")).duration_s > 0

    def test_captures_cost_from_an_agent_result(self):
        runner = EvalRunner(lambda q: FakeResult("x", cost=0.42), [])
        assert runner.run_one(EvalCase(id="1", input="q")).cost == 0.42

    def test_cost_defaults_to_zero_for_a_string(self):
        assert EvalRunner(lambda q: "x", []).run_one(EvalCase(id="1", input="q")).cost == 0.0


class TestErrorHandling:
    def test_a_crashing_agent_is_a_failed_case(self):
        def boom(question):
            raise RuntimeError("agent died")

        result = EvalRunner(boom, [contains("x")]).run_one(EvalCase(id="1", input="q"))
        assert not result.passed
        assert "RuntimeError" in result.error
        assert "agent died" in result.error

    def test_run_one_never_raises(self):
        def boom(question):
            raise KeyError("x")

        EvalRunner(boom, []).run_one(EvalCase(id="1", input="q"))

    def test_a_crashing_check_is_a_failed_check(self):
        def explode(output, case):
            raise ValueError("bad check")

        result = EvalRunner(perfect, [explode]).run_one(EvalCase(id="1", input="q1"))
        assert not result.passed
        assert result.error is None, "the AGENT was fine; only the check broke"
        assert any("check_error" == c.name for c in result.checks)

    def test_other_checks_still_run_after_one_raises(self):
        def explode(output, case):
            raise ValueError("bad")

        runner = EvalRunner(perfect, [explode, contains("answer")])
        result = runner.run_one(EvalCase(id="1", input="q1"))
        assert len(result.checks) == 2

    def test_one_bad_case_does_not_kill_the_suite(self):
        def sometimes(question):
            if question == "q1":
                raise RuntimeError("boom")
            return f"the answer is a{question[1:]}"

        report = EvalRunner(sometimes, [expected_contains()]).run(dataset(4))
        assert report.total == 4, "an eval suite that dies on case 2 of 200 is useless"
        assert report.errored == 1
        assert report.passed == 3


class TestRun:
    def test_report_covers_every_case(self):
        report = EvalRunner(perfect, [expected_contains()]).run(dataset(5))
        assert report.total == 5
        assert report.passed == 5

    def test_report_takes_the_dataset_name(self):
        assert EvalRunner(perfect, []).run(dataset()).name == "test-suite"

    def test_records_total_duration(self):
        assert EvalRunner(perfect, []).run(dataset()).duration_s >= 0

    def test_empty_dataset(self):
        report = EvalRunner(perfect, [contains("x")]).run(Dataset(name="empty"))
        assert report.total == 0
        assert report.pass_rate == 0.0

    def test_on_result_callback(self):
        seen = []
        EvalRunner(perfect, [], on_result=seen.append).run(dataset(3))
        assert len(seen) == 3

    def test_results_keep_dataset_order(self):
        # a report whose rows move between runs is miserable to diff
        import random

        def jittery(question):
            time.sleep(random.uniform(0, 0.03))
            return f"the answer is a{question[1:]}"

        report = EvalRunner(jittery, [], max_parallel=5).run(dataset(6))
        assert [r.case.id for r in report.results] == [str(i) for i in range(6)]

    def test_runs_in_parallel(self):
        def slow(question):
            time.sleep(0.1)
            return "x"

        started = time.monotonic()
        EvalRunner(slow, [], max_parallel=5).run(dataset(5))
        assert time.monotonic() - started < 0.35, "cases are independent; parallelise"

    def test_serial_when_max_parallel_is_one(self):
        def slow(question):
            time.sleep(0.05)
            return "x"

        started = time.monotonic()
        EvalRunner(slow, [], max_parallel=1).run(dataset(4))
        assert time.monotonic() - started >= 0.18

    def test_end_to_end_with_mixed_results(self):
        def half_right(question):
            return "the answer is a0" if question == "q0" else "no idea"

        report = EvalRunner(half_right, [expected_contains()]).run(dataset(4))
        assert report.passed == 1
        assert report.failed == 3
        assert report.failures_by_check() == {"expected_contains": 3}
        assert not report.meets(0.5)
