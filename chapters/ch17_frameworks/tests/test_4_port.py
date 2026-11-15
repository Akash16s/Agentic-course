"""Tests for Chapter 17, Exercise 4 — the ported agent."""

import pytest

from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool
from chapters.ch17_frameworks.exercises.exercise_4_port import (
    build_agent_graph,
    seed_state,
)


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def search(query: str) -> str:
    """Search for something."""
    return f"results for {query}"


REG = ToolRegistry([add_numbers, search])


class TestSeedState:
    def test_shape(self):
        state = seed_state("do a thing", system="be helpful")
        assert state["steps"] == 0
        assert state["output"] == ""
        assert state["calls"] == []

    def test_includes_the_system_prompt(self):
        state = seed_state("task", system="be helpful")
        assert state["messages"][0] == {"role": "system", "content": "be helpful"}

    def test_includes_the_task(self):
        state = seed_state("do a thing")
        assert state["messages"][-1]["content"] == "do a thing"

    def test_no_system_prompt(self):
        assert seed_state("task")["messages"][0]["role"] == "user"


class TestNoTools:
    def test_answers_directly(self):
        graph = build_agent_graph(FakeLLMClient(["Paris."]), ToolRegistry())
        result = graph.invoke(seed_state("capital of France?"))
        assert result.state["output"] == "Paris."
        assert result.path == ["think"]

    def test_counts_steps(self):
        graph = build_agent_graph(FakeLLMClient(["hi"]), ToolRegistry())
        assert graph.invoke(seed_state("q")).state["steps"] == 1


class TestWithTools:
    def test_one_tool_then_an_answer(self):
        client = FakeLLMClient([
            tool_response(tool_call("add_numbers", {"a": 2, "b": 3})),
            "The answer is 5.",
        ])
        result = build_agent_graph(client, REG).invoke(seed_state("2+3?"))
        assert result.path == ["think", "act", "think"]
        assert result.state["output"] == "The answer is 5."

    def test_tool_results_reach_the_messages(self):
        client = FakeLLMClient([
            tool_response(tool_call("add_numbers", {"a": 2, "b": 3})),
            "It is 5.",
        ])
        result = build_agent_graph(client, REG).invoke(seed_state("2+3?"))
        tool_messages = [m for m in result.state["messages"] if m["role"] == "tool"]
        assert tool_messages[0]["content"] == "5"

    def test_message_order_matches_the_chapter_3_agent(self):
        client = FakeLLMClient([
            tool_response(tool_call("add_numbers", {"a": 1, "b": 1})),
            "It is 2.",
        ])
        result = build_agent_graph(client, REG, system="sys").invoke(
            seed_state("1+1?", system="sys"))
        roles = [m["role"] for m in result.state["messages"]]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]

    def test_multi_step(self):
        client = FakeLLMClient([
            tool_response(tool_call("search", {"query": "a"})),
            tool_response(tool_call("search", {"query": "b"})),
            "Done.",
        ])
        result = build_agent_graph(client, REG).invoke(seed_state("go"))
        assert result.path == ["think", "act", "think", "act", "think"]
        assert result.state["steps"] == 3

    def test_parallel_calls_in_one_act(self):
        client = FakeLLMClient([
            tool_response(
                tool_call("search", {"query": "a"}, call_id="c1"),
                tool_call("search", {"query": "b"}, call_id="c2"),
            ),
            "Done.",
        ])
        result = build_agent_graph(client, REG).invoke(seed_state("go"))
        tool_messages = [m for m in result.state["messages"] if m["role"] == "tool"]
        assert len(tool_messages) == 2

    def test_a_tool_failure_does_not_stop_the_graph(self):
        @tool
        def broken() -> str:
            """Fails."""
            raise RuntimeError("nope")

        client = FakeLLMClient([
            tool_response(tool_call("broken", {})),
            "I could not do that.",
        ])
        result = build_agent_graph(client, ToolRegistry([broken])).invoke(
            seed_state("go"))
        assert result.state["output"] == "I could not do that."


class TestLimits:
    def test_max_steps_still_applies(self):
        # drawing a diagram does not make a loop terminate
        client = FakeLLMClient([tool_response(tool_call("search", {"query": "x"}))] * 50)
        result = build_agent_graph(client, REG).invoke(seed_state("go"), max_steps=6)
        assert result.stopped_early
        assert len(result.steps) == 6


class TestDiagram:
    def test_the_graph_can_be_drawn(self):
        graph = build_agent_graph(FakeLLMClient(["x"]), REG)
        mermaid = graph.graph.to_mermaid()
        assert "think" in mermaid and "act" in mermaid
