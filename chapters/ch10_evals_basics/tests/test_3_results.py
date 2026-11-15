"""Tests for Chapter 10, Exercise 3 — results and reporting."""

import pytest

from chapters.ch10_evals_basics.exercises.exercise_1_dataset import EvalCase
from chapters.ch10_evals_basics.exercises.exercise_2_checks import CheckResult
from chapters.ch10_evals_basics.exercises.exercise_3_results import (
    CaseResult,
    EvalReport,
)


def case(i="1"):
    return EvalCase(id=i, input=f"question {i}")


def result(i="1", checks=(), error=None, cost=0.0, duration=0.0, output="out"):
    return CaseResult(case=case(i), checks=list(checks), error=error,
                      cost=cost, duration_s=duration, output=output)


PASS = CheckResult("contains", True)
FAIL = CheckResult("contains", False, "'Paris' not in output")
FAIL2 = CheckResult("tool_called", False, "'search' never called")


class TestCaseResult:
    def test_passes_when_all_checks_pass(self):
        assert result(checks=[PASS, PASS]).passed

    def test_fails_when_any_check_fails(self):
        assert not result(checks=[PASS, FAIL]).passed

    def test_an_errored_case_is_a_failed_case(self):
        # letting errors drop out of the denominator is how a suite reports 100%
        # while half of it crashed
        assert not result(checks=[PASS], error="boom").passed

    def test_no_checks_passes(self):
        assert result(checks=[]).passed

    def test_failures_lists_only_the_failed(self):
        assert result(checks=[PASS, FAIL, FAIL2]).failures == [FAIL, FAIL2]


class TestEvalReport:
    def report(self):
        return EvalReport(name="suite", duration_s=10.0, results=[
            result("1", [PASS], cost=0.01, duration=0.2),
            result("2", [PASS], cost=0.02, duration=0.4),
            result("3", [FAIL], cost=0.03, duration=0.6),
            result("4", [FAIL, FAIL2], cost=0.04, duration=0.8),
            result("5", error="RuntimeError: boom", cost=0.0, duration=0.1),
        ])

    def test_counts(self):
        r = self.report()
        assert r.total == 5
        assert r.passed == 2
        assert r.failed == 3
        assert r.errored == 1

    def test_pass_rate(self):
        assert self.report().pass_rate == pytest.approx(0.4)

    def test_empty_report_does_not_divide_by_zero(self):
        empty = EvalReport(name="s")
        assert empty.pass_rate == 0.0
        assert empty.total == 0
        assert empty.p50_duration == 0.0

    def test_total_cost(self):
        assert self.report().total_cost == pytest.approx(0.10)

    def test_p50_is_the_median_not_the_mean(self):
        r = EvalReport(name="s", results=[
            result("1", duration=0.1), result("2", duration=0.1),
            result("3", duration=0.1), result("4", duration=40.0),
        ])
        assert r.p50_duration < 1.0, "one outlier must not make the suite look slow"

    def test_failures_by_check(self):
        counts = self.report().failures_by_check()
        assert counts["contains"] == 2
        assert counts["tool_called"] == 1

    def test_failures_by_check_is_sorted_most_frequent_first(self):
        r = EvalReport(name="s", results=[
            result("1", [CheckResult("rare", False)]),
            result("2", [CheckResult("common", False)]),
            result("3", [CheckResult("common", False)]),
            result("4", [CheckResult("common", False)]),
        ])
        assert list(r.failures_by_check()) == ["common", "rare"]

    def test_failures_by_check_empty_when_all_pass(self):
        r = EvalReport(name="s", results=[result("1", [PASS])])
        assert r.failures_by_check() == {}


class TestGate:
    def test_meets(self):
        r = self.make(8, 10)
        assert r.meets(0.8)
        assert r.meets(0.75)
        assert not r.meets(0.85)

    def test_exact_threshold_passes(self):
        assert self.make(8, 10).meets(0.8)

    @staticmethod
    def make(passed, total):
        results = [result(str(i), [PASS]) for i in range(passed)]
        results += [result(str(i), [FAIL]) for i in range(passed, total)]
        return EvalReport(name="s", results=results)


class TestOutput:
    def report(self):
        return EvalReport(name="support-v3", duration_s=18.4, results=[
            result("1", [PASS], cost=0.01, duration=0.3),
            result("2", [FAIL], cost=0.02, duration=0.4, output="Berlin"),
            result("3", error="RuntimeError: boom"),
        ])

    def test_summary_has_the_headline_numbers(self):
        out = self.report().summary()
        assert "support-v3" in out
        assert "1/3" in out or "1 /3" in out
        assert "33" in out          # the percentage

    def test_summary_mentions_errors(self):
        assert "error" in self.report().summary().lower()

    def test_summary_lists_failures_by_check(self):
        assert "contains" in self.report().summary()

    def test_summary_includes_cost(self):
        assert "0.03" in self.report().summary()

    def test_failure_detail_shows_the_failing_cases(self):
        out = self.report().failure_detail()
        assert "question 2" in out
        assert "'Paris' not in output" in out

    def test_failure_detail_shows_the_actual_output(self):
        # a failure you cannot see the output of is one you must re-run to understand
        assert "Berlin" in self.report().failure_detail()

    def test_failure_detail_shows_errors(self):
        assert "RuntimeError" in self.report().failure_detail()

    def test_failure_detail_skips_passes(self):
        assert "question 1" not in self.report().failure_detail()

    def test_failure_detail_is_bounded(self):
        many = EvalReport(name="s", results=[
            result(str(i), [FAIL], output="x" * 5000) for i in range(100)
        ])
        assert len(many.failure_detail(limit=5)) < 6000, "a report is for reading"
