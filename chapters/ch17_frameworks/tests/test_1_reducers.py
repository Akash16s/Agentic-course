"""Tests for Chapter 17, Exercise 1 — reducers."""

import pytest

from chapters.ch17_frameworks.exercises.exercise_1_reducers import (
    END,
    START,
    add,
    append,
    replace,
)


class TestSentinels:
    def test_distinct(self):
        assert START != END


class TestReplace:
    def test_update_wins(self):
        assert replace("old", "new") == "new"

    def test_from_none(self):
        assert replace(None, "new") == "new"

    def test_replaces_with_none(self):
        assert replace("old", None) is None


class TestAppend:
    def test_from_none_with_a_scalar(self):
        assert append(None, "a") == ["a"]

    def test_from_none_with_a_list(self):
        assert append(None, ["a", "b"]) == ["a", "b"]

    def test_scalar_onto_a_list(self):
        assert append(["a"], "b") == ["a", "b"]

    def test_list_onto_a_list(self):
        assert append(["a"], ["b", "c"]) == ["a", "b", "c"]

    def test_empty_update(self):
        assert append(["a"], []) == ["a"]

    def test_does_not_mutate_the_existing_list(self):
        # a node that mutates shared state makes runs unreplayable
        current = ["a"]
        append(current, "b")
        assert current == ["a"]

    def test_returns_a_new_list_from_none(self):
        update = ["a"]
        result = append(None, update)
        result.append("b")
        assert update == ["a"]

    def test_accumulates_across_calls(self):
        state = None
        for message in ["one", "two", "three"]:
            state = append(state, message)
        assert state == ["one", "two", "three"]

    def test_works_with_dicts(self):
        assert append([{"role": "user"}], {"role": "assistant"}) == [
            {"role": "user"}, {"role": "assistant"}
        ]


class TestAdd:
    def test_from_none(self):
        assert add(None, 1) == 1

    def test_accumulates(self):
        assert add(3, 2) == 5

    def test_floats(self):
        assert add(0.01, 0.02) == pytest.approx(0.03)

    def test_from_zero(self):
        assert add(0, 5) == 5

    def test_accumulates_across_calls(self):
        total = None
        for _ in range(4):
            total = add(total, 1)
        assert total == 4
