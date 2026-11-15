"""Tests for Chapter 9, Exercise 2 — validation."""

import pytest

from chapters.ch09_structured_output.exercises.exercise_2_validate import validate

PERSON = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 2},
        "age": {"type": "integer", "minimum": 0, "maximum": 150},
        "role": {"type": "string", "enum": ["dev", "pm", "design"]},
        "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "required": ["name", "age"],
}


class TestTypes:
    def test_valid(self):
        assert validate({"name": "Akash", "age": 30}, PERSON) == []

    def test_wrong_type(self):
        errors = validate({"name": "Akash", "age": "thirty"}, PERSON)
        assert len(errors) == 1
        assert "$.age" in errors[0] and "integer" in errors[0]

    def test_bool_is_not_an_integer(self):
        # isinstance(True, int) is True in Python. JSON disagrees.
        errors = validate({"name": "Akash", "age": True}, PERSON)
        assert errors, "True passed as an integer"

    def test_integer_is_a_valid_number(self):
        assert validate(5, {"type": "number"}) == []

    def test_float_is_not_an_integer(self):
        assert validate(5.5, {"type": "integer"})

    def test_null(self):
        assert validate(None, {"type": "null"}) == []
        assert validate(None, {"type": "string"})

    def test_union_types(self):
        schema = {"type": ["string", "null"]}
        assert validate("x", schema) == []
        assert validate(None, schema) == []
        assert validate(5, schema)

    def test_no_type_means_no_constraint(self):
        assert validate("anything", {}) == []

    def test_type_error_stops_further_checks(self):
        # checking minLength on an integer is noise, not information
        errors = validate(5, {"type": "string", "minLength": 100})
        assert len(errors) == 1


class TestRequired:
    def test_missing_field(self):
        errors = validate({"name": "Akash"}, PERSON)
        assert any("age" in e and "required" in e for e in errors)

    def test_all_missing_are_reported(self):
        errors = validate({}, PERSON)
        assert len(errors) == 2, "collect every error, not just the first"

    def test_present_but_null_counts_as_present(self):
        errors = validate({"name": "Akash", "age": None}, PERSON)
        assert not any("required" in e for e in errors)


class TestConstraints:
    def test_min_length(self):
        assert validate({"name": "A", "age": 5}, PERSON)

    def test_max_length(self):
        assert validate("toolong", {"type": "string", "maxLength": 3})

    def test_minimum(self):
        errors = validate({"name": "Akash", "age": -1}, PERSON)
        assert "below minimum" in errors[0]

    def test_maximum(self):
        assert validate({"name": "Akash", "age": 200}, PERSON)

    def test_enum(self):
        errors = validate({"name": "Akash", "age": 30, "role": "ceo"}, PERSON)
        assert "not one of" in errors[0]

    def test_valid_enum(self):
        assert validate({"name": "Akash", "age": 30, "role": "dev"}, PERSON) == []


class TestArrays:
    def test_item_types(self):
        errors = validate({"name": "A2", "age": 1, "tags": ["ok", 5]}, PERSON)
        assert any("$.tags[1]" in e for e in errors)

    def test_min_items(self):
        errors = validate({"name": "A2", "age": 1, "tags": []}, PERSON)
        assert any("at least" in e for e in errors)

    def test_max_items(self):
        assert validate([1, 2, 3], {"type": "array", "maxItems": 2})

    def test_nested_arrays(self):
        schema = {"type": "array", "items": {"type": "array",
                                             "items": {"type": "integer"}}}
        assert validate([[1, 2], [3]], schema) == []
        assert validate([[1], ["x"]], schema)


class TestAdditionalProperties:
    def test_extras_allowed_by_default(self):
        assert validate({"name": "Akash", "age": 30, "extra": 1}, PERSON) == []

    def test_extras_rejected_when_false(self):
        schema = {**PERSON, "additionalProperties": False}
        errors = validate({"name": "Akash", "age": 30, "extra": 1}, schema)
        assert any("unexpected" in e for e in errors)


class TestPaths:
    def test_nested_object_path(self):
        schema = {
            "type": "object",
            "properties": {"user": {"type": "object",
                                    "properties": {"age": {"type": "integer"}}}},
        }
        errors = validate({"user": {"age": "x"}}, schema)
        assert "$.user.age" in errors[0]

    def test_array_index_path(self):
        schema = {"type": "array", "items": {"type": "object",
                                             "properties": {"n": {"type": "integer"}}}}
        errors = validate([{"n": 1}, {"n": "x"}], schema)
        assert "$[1].n" in errors[0]

    def test_deeply_nested_path(self):
        schema = {"type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "price": {"type": "number"}}}}}}
        errors = validate({"items": [{"price": 1}, {"price": 2}, {"price": "x"}]},
                          schema)
        assert "$.items[2].price" in errors[0]


class TestErrorCollection:
    def test_every_problem_is_reported(self):
        schema = {**PERSON, "additionalProperties": False}
        bad = {"name": "A", "age": "x", "role": "ceo", "tags": [], "extra": 1}
        errors = validate(bad, schema)
        assert len(errors) >= 4, (
            "one round trip fixing four problems beats four fixing one each"
        )

    def test_never_raises(self):
        for data in [None, [], {}, "x", 5, {"a": {"b": {"c": [1]}}}]:
            validate(data, PERSON)
