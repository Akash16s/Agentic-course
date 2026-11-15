"""Tests for Chapter 2, Exercise 3 — function -> Tool."""

from typing import Literal

import pytest

from chapters.ch02_tools.exercises.exercise_3_build_tool import (
    Tool,
    ToolResult,
    build_tool,
    stringify,
    tool,
)


def sample(city: str, unit: Literal["c", "f"] = "c", days: int | None = None) -> str:
    """Look up the weather.

    Args:
        city: City name.
        unit: Temperature unit.
        days: Forecast length.
    """
    return f"{city} {unit} {days}"


class TestBuildTool:
    def test_name_and_description_from_the_function(self):
        t = build_tool(sample)
        assert t.name == "sample"
        assert t.description == "Look up the weather."

    def test_overrides(self):
        t = build_tool(sample, name="weather", description="custom")
        assert t.name == "weather"
        assert t.description == "custom"

    def test_falls_back_to_the_function_name(self):
        def undocumented(x: int):
            pass

        assert build_tool(undocumented).description == "undocumented"

    def test_properties(self):
        props = build_tool(sample).parameters["properties"]
        assert props["city"] == {"type": "string", "description": "City name."}
        assert props["unit"]["enum"] == ["c", "f"]
        assert props["days"]["type"] == "integer"

    def test_required_excludes_defaults_and_optionals(self):
        assert build_tool(sample).parameters["required"] == ["city"]

    def test_parameters_is_an_object_schema(self):
        params = build_tool(sample).parameters
        assert params["type"] == "object"
        assert set(params) == {"type", "properties", "required"}

    def test_skips_self(self):
        class Thing:
            def method(self, x: int):
                """Do it."""

        t = build_tool(Thing().method)
        assert "self" not in t.parameters["properties"]

    def test_skips_varargs_and_kwargs(self):
        def f(a: int, *args, **kwargs):
            """Do it."""

        props = build_tool(f).parameters["properties"]
        assert set(props) == {"a"}

    def test_unannotated_parameter_is_unconstrained(self):
        def f(a):
            """Do it."""

        assert build_tool(f).parameters["properties"]["a"] == {}
        assert build_tool(f).parameters["required"] == ["a"]

    def test_no_parameters(self):
        def f():
            """Do it."""

        params = build_tool(f).parameters
        assert params["properties"] == {}
        assert params["required"] == []


class TestSpec:
    def test_shape(self):
        spec = build_tool(sample).spec()
        assert spec["type"] == "function"
        assert set(spec["function"]) == {"name", "description", "parameters"}
        assert spec["function"]["name"] == "sample"

    def test_is_json_serialisable(self):
        import json

        json.dumps(build_tool(sample).spec())  # must not raise


class TestCall:
    def test_success(self):
        t = build_tool(sample)
        r = t.call({"city": "Delhi"})
        assert r.is_error is False
        assert "Delhi" in r.content

    def test_wrong_argument_name_is_an_error_result_not_an_exception(self):
        t = build_tool(sample)
        r = t.call({"town": "Delhi"})
        assert r.is_error
        assert "invalid arguments" in r.content

    def test_missing_required_argument(self):
        r = build_tool(sample).call({})
        assert r.is_error

    def test_tool_exception_becomes_an_error_result(self):
        def explode() -> str:
            """Boom."""
            raise RuntimeError("kaboom")

        r = build_tool(explode).call({})
        assert r.is_error
        assert "RuntimeError" in r.content
        assert "kaboom" in r.content

    def test_call_never_raises(self):
        def explode(x: int):
            """Boom."""
            raise KeyError("nope")

        build_tool(explode).call({"x": 1})       # must not raise
        build_tool(explode).call({"bad": 1})     # must not raise


class TestStringify:
    def test_str_passes_through(self):
        assert stringify("hello") == "hello"

    def test_dict_becomes_json_not_python_repr(self):
        got = stringify({"a": 1})
        assert got == '{"a": 1}', "single-quoted python repr confuses models"

    def test_list(self):
        assert stringify([1, 2]) == "[1, 2]"

    def test_numbers(self):
        assert stringify(42) == "42"

    def test_tool_result_unwraps(self):
        assert stringify(ToolResult("inner")) == "inner"

    def test_unserialisable_falls_back_to_str(self):
        class Weird:
            def __str__(self):
                return "weird-thing"

        assert "weird" in stringify(Weird())


class TestDecorator:
    def test_bare(self):
        @tool
        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        assert isinstance(add, Tool)
        assert add.name == "add"
        assert add.call({"a": 1, "b": 2}).content == "3"

    def test_with_arguments(self):
        @tool(name="sum2", description="Adds.")
        def add(a: int, b: int) -> int:
            """Ignored."""
            return a + b

        assert isinstance(add, Tool)
        assert add.name == "sum2"
        assert add.description == "Adds."
