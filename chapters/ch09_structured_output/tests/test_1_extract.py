"""Tests for Chapter 9, Exercise 1 — extraction."""

import pytest

from chapters.ch09_structured_output.exercises.exercise_1_extract import (
    candidates,
    extract_json,
    strip_trailing_commas,
)


class TestStripTrailingCommas:
    def test_object(self):
        assert strip_trailing_commas('{"a": 1,}') == '{"a": 1}'

    def test_array(self):
        assert strip_trailing_commas("[1, 2,]") == "[1, 2]"

    def test_with_whitespace(self):
        assert strip_trailing_commas('{"a": 1,\n  }') == '{"a": 1\n  }'

    def test_leaves_valid_json_alone(self):
        assert strip_trailing_commas('{"a": 1, "b": 2}') == '{"a": 1, "b": 2}'


class TestCandidates:
    def test_whole_string_is_first(self):
        assert candidates('{"a": 1}')[0] == '{"a": 1}'

    def test_includes_fenced_blocks(self):
        got = candidates('text\n```json\n{"a": 1}\n```\nmore')
        assert '{"a": 1}' in got

    def test_includes_the_brace_span(self):
        assert '{"a": 1}' in candidates('prefix {"a": 1} suffix')

    def test_deduplicates_preserving_order(self):
        got = candidates('{"a": 1}')
        assert len(got) == len(set(got))
        assert got[0] == '{"a": 1}'


class TestExtractJson:
    def test_clean_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_clean_array(self):
        assert extract_json("[1, 2, 3]") == [1, 2, 3]

    def test_whitespace(self):
        assert extract_json('  \n {"a": 1}  \n ') == {"a": 1}

    def test_fenced(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fenced_without_a_language(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_fenced_with_prose_around_it(self):
        raw = "Sure, here you go:\n```json\n{\"a\": 1}\n```\nLet me know if that helps!"
        assert extract_json(raw) == {"a": 1}

    def test_prose_before(self):
        assert extract_json('Here is the JSON: {"a": 1}') == {"a": 1}

    def test_prose_after(self):
        assert extract_json('{"a": 1} — hope that helps') == {"a": 1}

    def test_trailing_comma_in_object(self):
        assert extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_trailing_comma_in_array(self):
        assert extract_json('{"a": [1, 2,]}') == {"a": [1, 2]}

    def test_json_label(self):
        assert extract_json('json {"a": 1}') == {"a": 1}

    def test_nested(self):
        raw = '{"outer": {"inner": [1, {"deep": true}]}}'
        assert extract_json(raw)["outer"]["inner"][1]["deep"] is True

    def test_multiline_object_with_prose(self):
        raw = 'Analysis complete.\n\n{\n  "sentiment": "negative",\n  "urgency": 4\n}\n'
        assert extract_json(raw)["urgency"] == 4

    def test_empty(self):
        assert extract_json("") is None
        assert extract_json("   ") is None
        assert extract_json(None) is None

    def test_no_json_at_all(self):
        assert extract_json("I'm sorry, I can't help with that.") is None

    def test_irreparably_broken(self):
        assert extract_json('{"a": 1, "b":') is None

    def test_never_raises(self):
        for raw in ["", "{", "}", "[", "null junk", "```", "{'a': 1}", "{a: 1}"]:
            extract_json(raw)

    def test_scalars_pass_through(self):
        assert extract_json("42") == 42
        assert extract_json('"hello"') == "hello"
        assert extract_json("true") is True
