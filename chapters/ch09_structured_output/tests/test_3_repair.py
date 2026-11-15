"""Tests for Chapter 9, Exercise 3 — the repair loop."""

import json

import pytest

from chapters.ch09_structured_output.exercises.exercise_3_repair import (
    ExtractResult,
    extract_validated,
    repair_prompt,
)

SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
}


class TestExtractResult:
    def test_ok(self):
        assert ExtractResult(value={"a": 1}).ok

    def test_not_ok_with_errors(self):
        assert not ExtractResult(value={"a": 1}, errors=["bad"]).ok

    def test_not_ok_without_a_value(self):
        assert not ExtractResult().ok


class TestRepairPrompt:
    def test_lists_the_errors(self):
        out = repair_prompt(["$.age: expected integer, got str"], SCHEMA, "{}")
        assert "$.age" in out
        assert "expected integer" in out

    def test_lists_every_error(self):
        out = repair_prompt(["error one", "error two"], SCHEMA, "{}")
        assert "error one" in out and "error two" in out

    def test_includes_the_schema(self):
        assert "age" in repair_prompt(["x"], SCHEMA, "{}")

    def test_unparseable_case_shows_what_was_sent(self):
        out = repair_prompt([], SCHEMA, "I cannot do that")
        assert "I cannot do that" in out
        assert "not valid JSON" in out

    def test_truncates_a_huge_bad_response(self):
        out = repair_prompt([], SCHEMA, "x" * 50_000)
        assert len(out) < 3_000, "don't pay to read 50k of wrong output back"

    def test_asks_for_json_only(self):
        assert "ONLY" in repair_prompt(["x"], SCHEMA, "{}")


class TestExtractValidated:
    def test_success_first_try(self):
        calls = []

        def call(feedback):
            calls.append(feedback)
            return '{"name": "Akash", "age": 30}'

        result = extract_validated(call, SCHEMA)
        assert result.ok
        assert result.value == {"name": "Akash", "age": 30}
        assert result.attempts == 1
        assert calls == [None], "no repair call when the first answer is good"

    def test_repairs_a_validation_error(self):
        responses = iter(['{"name": "Akash", "age": "thirty"}',
                          '{"name": "Akash", "age": 30}'])
        seen = []

        def call(feedback):
            seen.append(feedback)
            return next(responses)

        result = extract_validated(call, SCHEMA)
        assert result.ok
        assert result.attempts == 2
        assert seen[1] is not None and "$.age" in seen[1]

    def test_repairs_unparseable_output(self):
        responses = iter(["I'm not sure I can do that.",
                          '{"name": "Akash", "age": 30}'])
        result = extract_validated(lambda f: next(responses), SCHEMA)
        assert result.ok
        assert result.attempts == 2

    def test_gives_up_after_max_attempts(self):
        result = extract_validated(lambda f: "nope", SCHEMA, max_attempts=3)
        assert not result.ok
        assert result.attempts == 3
        assert result.errors

    def test_reports_the_last_errors(self):
        result = extract_validated(lambda f: '{"name": "Akash"}', SCHEMA,
                                   max_attempts=2)
        assert any("age" in e for e in result.errors)

    def test_keeps_the_last_raw_response(self):
        result = extract_validated(lambda f: "garbage", SCHEMA, max_attempts=1)
        assert result.raw == "garbage"

    def test_never_raises(self):
        for response in ["", "{", "null", "[]", '{"name": 1}']:
            extract_validated(lambda f: response, SCHEMA, max_attempts=2)

    def test_partial_value_is_still_returned(self):
        # the caller may want to see what the model DID produce
        result = extract_validated(lambda f: '{"name": "Akash"}', SCHEMA,
                                   max_attempts=1)
        assert result.value == {"name": "Akash"}
        assert not result.ok

    def test_max_attempts_one_means_no_repair(self):
        calls = []
        extract_validated(lambda f: calls.append(f) or "bad", SCHEMA, max_attempts=1)
        assert calls == [None]

    def test_handles_fenced_responses(self):
        result = extract_validated(
            lambda f: '```json\n{"name": "Akash", "age": 30}\n```', SCHEMA
        )
        assert result.ok
