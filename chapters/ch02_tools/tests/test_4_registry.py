"""Tests for Chapter 2, Exercise 4 — the registry."""

import pytest

from chapters.ch02_tools.exercises.exercise_3_build_tool import build_tool, tool
from chapters.ch02_tools.exercises.exercise_4_registry import ToolRegistry


def _add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.
    """
    return a + b


def _greet(name: str) -> str:
    """Greet someone."""
    return f"hi {name}"


# Exercise 4 builds on Exercise 3. Rather than exploding during collection with a
# NotImplementedError from build_tool, say so.
try:
    add = build_tool(_add, name="add")
    greet = build_tool(_greet, name="greet")
except NotImplementedError:  # pragma: no cover
    pytest.skip("finish exercise 3 first", allow_module_level=True)


class TestRegistration:
    def test_empty(self):
        r = ToolRegistry()
        assert len(r) == 0
        assert r.names == []
        assert r.specs() == []

    def test_from_constructor(self):
        r = ToolRegistry([add, greet])
        assert len(r) == 2
        assert r.names == ["add", "greet"], "registration order should be preserved"

    def test_register_a_plain_function(self):
        r = ToolRegistry()

        def double(x: int) -> int:
            """Double it."""
            return x * 2

        t = r.register(double)
        assert t.name == "double"
        assert "double" in r

    def test_duplicate_names_raise(self):
        r = ToolRegistry([add])
        with pytest.raises(ValueError):
            r.register(add)

    def test_contains_and_get(self):
        r = ToolRegistry([add])
        assert "add" in r
        assert "nope" not in r
        assert r.get("add") is not None
        assert r.get("nope") is None

    def test_specs_match_tool_count(self):
        r = ToolRegistry([add, greet])
        specs = r.specs()
        assert len(specs) == 2
        assert {s["function"]["name"] for s in specs} == {"add", "greet"}


class TestExecute:
    def test_dict_arguments(self):
        r = ToolRegistry([add])
        assert r.execute("add", {"a": 2, "b": 3}).content == "5"

    def test_json_string_arguments(self):
        r = ToolRegistry([add])
        assert r.execute("add", '{"a": 2, "b": 3}').content == "5"

    def test_empty_string_arguments_means_no_arguments(self):
        r = ToolRegistry()

        @tool
        def now() -> str:
            """Current time."""
            return "12:00"

        r.register(now)
        assert r.execute("now", "").content == "12:00"
        assert r.execute("now", "   ").content == "12:00"

    def test_unknown_tool_lists_the_real_ones(self):
        r = ToolRegistry([add, greet])
        result = r.execute("subtract", {})
        assert result.is_error
        assert "subtract" in result.content
        assert "add" in result.content and "greet" in result.content

    def test_unknown_tool_on_empty_registry(self):
        result = ToolRegistry().execute("anything", {})
        assert result.is_error
        assert "none" in result.content

    def test_malformed_json(self):
        r = ToolRegistry([add])
        result = r.execute("add", '{"a": 2, "b":')
        assert result.is_error
        assert "not valid JSON" in result.content

    def test_json_that_is_not_an_object(self):
        r = ToolRegistry([add])
        result = r.execute("add", "[1, 2]")
        assert result.is_error
        assert "object" in result.content

    def test_tool_error_propagates_as_a_result(self):
        r = ToolRegistry([add])
        result = r.execute("add", {"a": "not a number", "b": 1})
        assert result.is_error

    def test_execute_never_raises(self):
        r = ToolRegistry([add])
        for args in [{}, "", "{bad", "[1]", {"z": 9}, "null", '"a string"']:
            r.execute("add", args)
            r.execute("missing", args)
