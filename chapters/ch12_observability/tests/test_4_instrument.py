"""Tests for Chapter 12, Exercise 4 — instrumentation."""

import pytest

from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool
from chapters.ch12_observability.exercises.exercise_3_analysis import AnalysingTracer
from chapters.ch12_observability.exercises.exercise_4_instrument import (
    TracedClient,
    TracedRegistry,
)


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def boom() -> str:
    """Always fails."""
    raise RuntimeError("tool exploded")


class TestTracedClient:
    def test_creates_a_span(self):
        t = AnalysingTracer()
        TracedClient(FakeLLMClient(["hi"]), t).chat([{"role": "user", "content": "q"}])
        assert len(t.spans) == 1
        assert t.spans[0].name == "llm.chat"
        assert t.spans[0].kind == "llm"

    def test_returns_the_response_unchanged(self):
        t = AnalysingTracer()
        response = TracedClient(FakeLLMClient(["hello"]), t).chat([])
        assert response.text == "hello"

    def test_records_usage(self):
        t = AnalysingTracer()
        TracedClient(FakeLLMClient(["hi"]), t).chat([])
        attributes = t.spans[0].attributes
        assert attributes["prompt_tokens"] == 10
        assert attributes["completion_tokens"] == 5
        assert attributes["total_tokens"] == 15

    def test_records_cost(self):
        t = AnalysingTracer()
        TracedClient(FakeLLMClient(["hi"]), t).chat([])
        assert t.spans[0].attributes["cost_usd"] > 0

    def test_records_message_count_not_content(self):
        # what you log matters: contents are huge and often sensitive
        t = AnalysingTracer()
        TracedClient(FakeLLMClient(["hi"]), t).chat(
            [{"role": "user", "content": "my secret password is hunter2"}]
        )
        assert t.spans[0].attributes["messages"] == 1
        assert "hunter2" not in str(t.spans[0].attributes)

    def test_records_finish_reason_and_tool_call_count(self):
        t = AnalysingTracer()
        client = TracedClient(
            FakeLLMClient([tool_response(tool_call("add", {"a": 1, "b": 2}))]), t
        )
        client.chat([])
        assert t.spans[0].attributes["finish_reason"] == "tool_calls"
        assert t.spans[0].attributes["tool_calls"] == 1

    def test_records_the_model(self):
        t = AnalysingTracer()
        TracedClient(FakeLLMClient(["hi"]), t).chat([], model="my-model")
        assert t.spans[0].attributes["model"] == "my-model"

    def test_delegates_unknown_attributes(self):
        t = AnalysingTracer()
        inner = FakeLLMClient(["hi"])
        traced = TracedClient(inner, t)
        assert traced.model == inner.model
        assert traced.call_count == 0

    def test_nests_under_an_open_span(self):
        t = AnalysingTracer()
        client = TracedClient(FakeLLMClient(["hi"]), t)
        with t.span("agent.run", kind="agent") as root:
            client.chat([])
        assert t.spans[1].parent_id == root.span_id

    def test_errors_propagate_and_are_recorded(self):
        t = AnalysingTracer()
        client = TracedClient(FakeLLMClient([RuntimeError("api down")]), t)
        with pytest.raises(RuntimeError):
            client.chat([])
        assert t.spans[0].status == "error"


class TestTracedRegistry:
    def test_creates_a_span_per_execution(self):
        t = AnalysingTracer()
        TracedRegistry(ToolRegistry([add]), t).execute("add", {"a": 1, "b": 2})
        assert t.spans[0].name == "tool.add"
        assert t.spans[0].kind == "tool"

    def test_returns_the_result_unchanged(self):
        t = AnalysingTracer()
        result = TracedRegistry(ToolRegistry([add]), t).execute("add", {"a": 1, "b": 2})
        assert result.content == "3"

    def test_records_the_tool_name_and_arguments(self):
        t = AnalysingTracer()
        TracedRegistry(ToolRegistry([add]), t).execute("add", {"a": 1, "b": 2})
        assert t.spans[0].attributes["tool"] == "add"
        assert "1" in t.spans[0].attributes["arguments"]

    def test_records_result_size(self):
        t = AnalysingTracer()
        TracedRegistry(ToolRegistry([add]), t).execute("add", {"a": 1, "b": 2})
        assert t.spans[0].attributes["result_chars"] == 1

    def test_truncates_huge_arguments(self):
        t = AnalysingTracer()
        TracedRegistry(ToolRegistry([add]), t).execute("add", {"a": "x" * 50_000})
        assert len(t.spans[0].attributes["arguments"]) <= 200

    def test_tool_error_marks_the_span(self):
        t = AnalysingTracer()
        TracedRegistry(ToolRegistry([boom]), t).execute("boom", {})
        assert t.spans[0].status == "error"
        assert "RuntimeError" in t.spans[0].error

    def test_tool_error_still_returns_normally(self):
        # Chapter 2's rule stands: tool failures are DATA for the model.
        # The span error is for you.
        t = AnalysingTracer()
        result = TracedRegistry(ToolRegistry([boom]), t).execute("boom", {})
        assert result.is_error
        assert isinstance(result.content, str)

    def test_delegates_unknown_attributes(self):
        t = AnalysingTracer()
        traced = TracedRegistry(ToolRegistry([add]), t)
        assert traced.names == ["add"]
        assert len(traced.specs()) == 1


class TestTogether:
    def test_a_full_agent_run_produces_a_tree(self):
        from agentlib.agent import Agent

        t = AnalysingTracer()
        client = TracedClient(
            FakeLLMClient([tool_response(tool_call("add", {"a": 2, "b": 3})),
                           "The answer is 5."]),
            t,
        )
        registry = ToolRegistry([add])
        with t.span("agent.run", kind="agent") as root:
            result = Agent(client, tools=registry).run("2+3?")
            root.set(steps=result.step_count)

        assert len(t.root_spans) == 1
        assert len(t.children_of(root.span_id)) == 2       # two llm calls
        assert t.sum_attribute("cost_usd") > 0
        assert "llm.chat" in t.render()
