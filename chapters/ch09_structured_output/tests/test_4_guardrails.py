"""Tests for Chapter 9, Exercise 4 — guardrails."""

import pytest

from chapters.ch09_structured_output.exercises.exercise_4_guardrails import (
    Blocklist,
    GuardResult,
    Guardrail,
    MaxLength,
    RedactPII,
    run_guardrails,
)


class TestMaxLength:
    def test_within_limit(self):
        r = MaxLength(100).check("short")
        assert r.passed and r.value == "short"

    def test_over_limit_rejects(self):
        r = MaxLength(5).check("far too long")
        assert not r.passed
        assert "limit 5" in r.reason

    def test_over_limit_truncates(self):
        r = MaxLength(5, truncate=True).check("far too long")
        assert r.passed
        assert r.value == "far t"
        assert r.reason == "truncated"

    def test_non_string_input(self):
        assert MaxLength(100).check({"a": 1}).passed

    def test_exact_length_passes(self):
        assert MaxLength(5).check("12345").passed


class TestBlocklist:
    def test_clean(self):
        assert Blocklist(["secret"]).check("all fine here").passed

    def test_blocked(self):
        r = Blocklist(["secret"]).check("this is secret")
        assert not r.passed
        assert "secret" in r.reason

    def test_case_insensitive(self):
        assert not Blocklist(["secret"]).check("This Is SECRET").passed

    def test_reports_every_hit(self):
        r = Blocklist(["alpha", "beta", "gamma"]).check("alpha and beta")
        assert "alpha" in r.reason and "beta" in r.reason
        assert "gamma" not in r.reason

    def test_empty_blocklist(self):
        assert Blocklist([]).check("anything").passed

    def test_value_is_unchanged(self):
        assert Blocklist(["x"]).check("contains x").value == "contains x"


class TestRedactPII:
    def test_email(self):
        r = RedactPII().check("write to akash@example.com")
        assert "akash@example.com" not in r.value
        assert "[EMAIL]" in r.value

    def test_ssn(self):
        assert "[SSN]" in RedactPII().check("SSN 123-45-6789").value

    def test_always_passes(self):
        # the point is to make output safe, not to withhold it
        assert RedactPII().check("akash@example.com").passed

    def test_reports_what_was_redacted(self):
        r = RedactPII().check("a@b.com and c@d.com")
        assert "email" in r.reason

    def test_clean_text_has_no_reason(self):
        assert RedactPII().check("nothing sensitive here").reason == ""

    def test_selected_kinds_only(self):
        r = RedactPII(kinds=["email"]).check("a@b.com and 123-45-6789")
        assert "[EMAIL]" in r.value
        assert "123-45-6789" in r.value

    def test_unknown_kind_is_ignored(self):
        RedactPII(kinds=["not_a_real_kind"]).check("text")   # must not raise


class TestRunGuardrails:
    def test_all_pass(self):
        report = run_guardrails("clean text", [MaxLength(100), Blocklist(["bad"])])
        assert report.passed
        assert report.failures == []

    def test_one_failure(self):
        report = run_guardrails("this is bad", [MaxLength(100), Blocklist(["bad"])])
        assert not report.passed
        assert len(report.failures) == 1

    def test_every_guard_runs_even_after_a_failure(self):
        report = run_guardrails("bad and worse", [Blocklist(["bad"]),
                                                  Blocklist(["worse"])])
        assert len(report.failures) == 2, "report all the problems, not just the first"

    def test_value_is_threaded_through(self):
        report = run_guardrails("email a@b.com and more text here",
                                [RedactPII(), MaxLength(20, truncate=True)])
        assert "[EMAIL]" in report.value
        assert len(report.value) <= 20

    def test_order_matters_redact_then_block(self):
        # redact first: the email is gone before the blocklist sees it
        good = run_guardrails("contact a@b.com", [RedactPII(), Blocklist(["@"])])
        assert good.passed

        # block first: it rejects text that redaction would have made fine
        bad = run_guardrails("contact a@b.com", [Blocklist(["@"]), RedactPII()])
        assert not bad.passed

    def test_notes_record_rewrites(self):
        report = run_guardrails("a@b.com", [RedactPII()])
        assert report.notes and "redact_pii" in report.notes[0]

    def test_no_guards(self):
        report = run_guardrails("anything", [])
        assert report.passed and report.value == "anything"
