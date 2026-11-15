"""Tests for Chapter 11, Exercise 4 — statistics."""

import random

import pytest

from agentlib.evals.core import CaseResult, CheckResult, EvalCase, EvalReport
from chapters.ch11_evals_judges.exercises.exercise_4_stats import (
    bootstrap_ci,
    compare_runs,
)


def report(name, outcomes):
    """outcomes: dict of case id -> passed."""
    return EvalReport(name=name, results=[
        CaseResult(case=EvalCase(id=case_id, input="q"),
                   checks=[CheckResult("c", passed)])
        for case_id, passed in outcomes.items()
    ])


class TestBootstrapCI:
    def test_brackets_the_observed_rate(self):
        low, high = bootstrap_ci(42, 50)
        assert low < 0.84 < high

    def test_the_interval_is_wide_at_n_50(self):
        # the headline point of the chapter
        low, high = bootstrap_ci(42, 50)
        assert high - low > 0.12, f"expected a wide interval, got {low:.2f}-{high:.2f}"

    def test_more_cases_narrow_it(self):
        small = bootstrap_ci(84, 100)
        large = bootstrap_ci(840, 1000)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_an_84_to_88_change_is_inside_the_noise(self):
        low, high = bootstrap_ci(42, 50)
        assert low <= 0.88 <= high, "n=50 cannot distinguish 84% from 88%"

    def test_all_pass(self):
        low, high = bootstrap_ci(50, 50)
        assert low == 1.0 and high == 1.0

    def test_all_fail(self):
        assert bootstrap_ci(0, 50) == (0.0, 0.0)

    def test_zero_total(self):
        assert bootstrap_ci(0, 0) == (0.0, 0.0)

    def test_deterministic_by_default(self):
        assert bootstrap_ci(42, 50) == bootstrap_ci(42, 50)

    def test_seeded_rng_is_respected(self):
        a = bootstrap_ci(42, 50, rng=random.Random(1))
        b = bootstrap_ci(42, 50, rng=random.Random(1))
        assert a == b

    def test_confidence_level_changes_the_width(self):
        wide = bootstrap_ci(42, 50, confidence=0.99)
        narrow = bootstrap_ci(42, 50, confidence=0.80)
        assert (wide[1] - wide[0]) >= (narrow[1] - narrow[0])


class TestCompareRuns:
    def test_clear_improvement(self):
        base = report("b", {str(i): i < 5 for i in range(10)})
        cand = report("c", {str(i): i < 9 for i in range(10)})
        result = compare_runs(base, cand)
        assert result.delta == pytest.approx(0.4)
        assert len(result.improved) == 4
        assert result.regressed == []

    def test_identifies_regressions(self):
        base = report("b", {"1": True, "2": True, "3": False})
        cand = report("c", {"1": True, "2": False, "3": True})
        result = compare_runs(base, cand)
        assert result.improved == ["3"]
        assert result.regressed == ["2"]

    def test_churn_is_visible_when_the_rate_is_flat(self):
        # THE headline case: 42/50 -> 42/50 looks like nothing happened
        base = report("b", {str(i): i < 8 for i in range(16)})
        cand = report("c", {str(i): not (i < 8) for i in range(16)})
        result = compare_runs(base, cand)
        assert result.delta == 0.0
        assert len(result.improved) == 8
        assert len(result.regressed) == 8

    def test_churn_is_called_out_in_the_note(self):
        base = report("b", {"1": True, "2": False})
        cand = report("c", {"1": False, "2": True})
        assert "churn" in compare_runs(base, cand).note.lower()

    def test_significance_needs_enough_flips(self):
        base = report("b", {str(i): i < 5 for i in range(10)})
        cand = report("c", {str(i): i < 6 for i in range(10)})
        assert not compare_runs(base, cand).significant

    def test_significant_when_many_flip_one_way(self):
        base = report("b", {str(i): False for i in range(10)})
        cand = report("c", {str(i): True for i in range(10)})
        assert compare_runs(base, cand).significant

    def test_min_flips_is_configurable(self):
        base = report("b", {"1": False, "2": False})
        cand = report("c", {"1": True, "2": True})
        assert compare_runs(base, cand, min_flips=2).significant
        assert not compare_runs(base, cand, min_flips=5).significant

    def test_only_shared_ids_are_compared(self):
        base = report("b", {"1": True, "2": True})
        cand = report("c", {"2": False, "3": True})
        result = compare_runs(base, cand)
        assert result.regressed == ["2"]
        assert "3" not in result.improved

    def test_no_shared_ids_is_flagged(self):
        base = report("b", {"1": True})
        cand = report("c", {"2": True})
        assert "common" in compare_runs(base, cand).note

    def test_identical_runs(self):
        base = report("b", {"1": True, "2": False})
        cand = report("c", {"1": True, "2": False})
        result = compare_runs(base, cand)
        assert result.delta == 0.0
        assert result.improved == [] and result.regressed == []

    def test_rates_are_reported(self):
        base = report("b", {"1": True, "2": False})
        cand = report("c", {"1": True, "2": True})
        result = compare_runs(base, cand)
        assert result.baseline_rate == 0.5
        assert result.candidate_rate == 1.0
