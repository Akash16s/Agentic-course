"""Tests for Chapter 2, Exercise 1 — type -> JSON Schema."""

from typing import Any, Literal, Optional, Union

import pytest

from chapters.ch02_tools.exercises.exercise_1_schema import (
    is_optional,
    python_type_to_json_schema,
)

f = python_type_to_json_schema


class TestSimpleTypes:
    @pytest.mark.parametrize(
        "tp,expected",
        [(str, "string"), (int, "integer"), (float, "number"), (bool, "boolean")],
    )
    def test_scalars(self, tp, expected):
        assert f(tp) == {"type": expected}

    def test_float_is_number_not_float(self):
        # JSON Schema has no "float". Getting this wrong makes providers reject the spec.
        assert f(float)["type"] == "number"

    def test_any_is_unconstrained(self):
        assert f(Any) == {}


class TestContainers:
    def test_list_of_ints(self):
        assert f(list[int]) == {"type": "array", "items": {"type": "integer"}}

    def test_list_of_strings(self):
        assert f(list[str]) == {"type": "array", "items": {"type": "string"}}

    def test_bare_list(self):
        assert f(list) == {"type": "array", "items": {}}

    def test_dict(self):
        assert f(dict[str, int]) == {"type": "object"}

    def test_nested(self):
        assert f(list[list[int]]) == {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}},
        }


class TestLiteral:
    def test_becomes_an_enum(self):
        assert f(Literal["a", "b"]) == {"type": "string", "enum": ["a", "b"]}

    def test_preserves_order(self):
        assert f(Literal["z", "a", "m"])["enum"] == ["z", "a", "m"]


class TestUnions:
    def test_pep604_optional(self):
        # The one that silently breaks if you only check typing.Union.
        assert f(int | None) == {"type": "integer"}

    def test_typing_optional(self):
        assert f(Optional[str]) == {"type": "string"}

    def test_real_union_uses_anyof(self):
        assert f(Union[int, str]) == {
            "anyOf": [{"type": "integer"}, {"type": "string"}]
        }

    def test_optional_union_drops_none_only(self):
        got = f(Union[int, str, None])
        assert got == {"anyOf": [{"type": "integer"}, {"type": "string"}]}


class TestFallback:
    def test_unknown_type_becomes_string(self):
        class Weird:
            pass

        assert f(Weird) == {"type": "string"}


class TestIsOptional:
    @pytest.mark.parametrize("tp", [int | None, Optional[str], Union[int, None]])
    def test_optional(self, tp):
        assert is_optional(tp)

    @pytest.mark.parametrize("tp", [int, str, list[int], Union[int, str]])
    def test_not_optional(self, tp):
        assert not is_optional(tp)
