"""Tests for Chapter 8b, Exercise 3 — subagents with isolated context."""

import pytest

from agentlib.agent import Agent, AgentResult, StopReason
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool
from chapters.ch08b_harness.exercises.exercise_3_subagents import (
    SUBAGENT_SYSTEM,
    SubagentResult,
    SubagentRunner,
    condense,
)

BIG_FILE = "line of a very large file\n" * 2_000      # ~52k chars


@tool
def read_file(path: str) -> str:
    """Read a file."""
    return BIG_FILE


@tool
def search(query: str) -> str:
    """Search for something."""
    return f"results for {query}"


@tool
def delete_everything() -> str:
    """Delete all the things."""
    return "deleted"


TOOLS = ToolRegistry([read_file, search, delete_everything])


def tool_names(kwargs):
    return [t["function"]["name"] for t in (kwargs.get("tools") or [])]


class TestSubagentResult:
    def test_ok(self):
        assert SubagentResult("t", "out", "done").ok
        assert SubagentResult("t", "out", "stop_tool").ok
        assert not SubagentResult("t", "out", "max_steps").ok
        assert not SubagentResult("t", "out", "done", error="boom").ok


class TestCondense:
    def test_short_output_unchanged(self):
        assert condense(AgentResult("X is 42", StopReason.DONE), 100) == "X is 42"

    def test_long_output_is_cut_to_the_limit(self):
        out = condense(AgentResult("y" * 10_000, StopReason.DONE), 500)
        assert len(out) <= 500

    def test_empty_output_gets_a_placeholder(self):
        assert "no output" in condense(AgentResult("  ", StopReason.DONE), 100)

    def test_partial_runs_are_labelled(self):
        out = condense(AgentResult("half an answer", StopReason.MAX_STEPS), 100)
        assert out.startswith("[subagent stopped early: max_steps]")
        assert "half an answer" in out


class TestRun:
    def test_child_gets_a_fresh_conversation(self):
        child = FakeLLMClient(["X is 42"])
        SubagentRunner(child, TOOLS).run("find X")
        assert child.calls[0][0] == [
            {"role": "system", "content": SUBAGENT_SYSTEM},
            {"role": "user", "content": "find X"},
        ]

    def test_returns_the_condensed_answer_and_the_numbers(self):
        child = FakeLLMClient([tool_response(tool_call("search", {"query": "x"})), "X is 42"])
        r = SubagentRunner(child, TOOLS).run("find X")
        assert r.ok
        assert r.output == "X is 42"
        assert r.stop_reason == "done"
        assert r.steps == 2
        assert r.tokens == 30          # two calls x Usage(10, 5)
        assert r.cost > 0
        assert r.task == "find X"

    def test_output_is_truncated(self):
        child = FakeLLMClient(["z" * 10_000])
        r = SubagentRunner(child, TOOLS, max_result_chars=300).run("t")
        assert len(r.output) <= 300

    def test_tools_are_restricted_to_the_subset(self):
        child = FakeLLMClient(["ok"])
        SubagentRunner(child, TOOLS).run("t", tools=["search"])
        assert tool_names(child.calls[0][1]) == ["search"]

    def test_none_means_every_parent_tool(self):
        child = FakeLLMClient(["ok"])
        SubagentRunner(child, TOOLS).run("t")
        assert tool_names(child.calls[0][1]) == ["read_file", "search", "delete_everything"]

    def test_empty_list_means_no_tools(self):
        child = FakeLLMClient(["ok"])
        SubagentRunner(child, TOOLS).run("t", tools=[])
        assert tool_names(child.calls[0][1]) == []

    def test_unknown_tool_is_an_error_result_not_an_exception(self):
        child = FakeLLMClient(["ok"])
        r = SubagentRunner(child, TOOLS).run("t", tools=["search", "launch_missiles"])
        assert not r.ok
        assert "launch_missiles" in r.output
        assert child.call_count == 0, "do not start a child with a bad toolset"

    def test_max_steps_is_passed_to_the_child(self):
        child = FakeLLMClient([tool_response(tool_call("search", {"query": "x"}))] * 20)
        r = SubagentRunner(child, TOOLS, max_steps=3).run("t")
        assert r.steps == 3
        assert r.stop_reason == "max_steps"
        assert not r.ok
        assert r.output.startswith("[subagent stopped early: max_steps]")

    def test_results_are_recorded_and_cost_is_totalled(self):
        seen = []
        runner = SubagentRunner(FakeLLMClient(["a", "b"]), TOOLS, on_result=seen.append)
        runner.run("one")
        runner.run("two")
        assert [r.task for r in runner.results] == ["one", "two"]
        assert seen == runner.results
        assert runner.total_cost == pytest.approx(sum(r.cost for r in runner.results))


class TestDepth:
    def test_default_depth_child_cannot_delegate(self):
        child = FakeLLMClient(["ok"])
        runner = SubagentRunner(child, ToolRegistry([search]))
        ToolRegistry([search, runner.as_tool()])         # the parent has delegate...
        runner.run("t")
        assert "delegate" not in tool_names(child.calls[0][1])   # ...the child does not

    def test_delegate_is_never_copied_from_the_parent_registry(self):
        inner = SubagentRunner(FakeLLMClient(), ToolRegistry([search]))
        parent_tools = ToolRegistry([search, inner.as_tool()])
        child = FakeLLMClient(["ok"])
        SubagentRunner(child, parent_tools).run("t", tools=["search", "delegate"])
        assert tool_names(child.calls[0][1]) == ["search"]

    def test_max_depth_two_gives_the_child_its_own_delegate(self):
        child = FakeLLMClient(["ok"])
        SubagentRunner(child, ToolRegistry([search]), max_depth=2).run("t")
        assert tool_names(child.calls[0][1]) == ["search", "delegate"]

    def test_runner_at_max_depth_refuses_without_calling_the_model(self):
        child = FakeLLMClient(["ok"])
        r = SubagentRunner(child, TOOLS, depth=1, max_depth=1).run("t")
        assert not r.ok
        assert "depth" in r.output
        assert child.call_count == 0


class TestAsTool:
    def test_spec(self):
        spec = SubagentRunner(FakeLLMClient(), TOOLS).as_tool().spec()["function"]
        assert spec["name"] == "delegate"
        assert spec["parameters"]["required"] == ["task"]
        assert spec["parameters"]["properties"]["tools"]["type"] == "array"
        assert "search" in spec["description"], "tell the parent which tools exist"

    def test_parent_and_child_contexts_are_isolated(self):
        """The test that matters. The child must never see the parent's history, and
        the parent must see only the child's condensed answer — not its tool output."""
        child = FakeLLMClient([
            tool_response(tool_call("read_file", {"path": "big.log"})),
            "The error is on line 1,204: disk full.",
        ])
        runner = SubagentRunner(child, TOOLS)
        parent = FakeLLMClient([
            tool_response(tool_call("delegate", {"task": "Find the error in big.log",
                                                 "tools": ["read_file"]})),
            "Fixed: the disk was full.",
        ])
        agent = Agent(parent, tools=ToolRegistry([search, runner.as_tool()]),
                      system="PARENT SYSTEM PROMPT")
        result = agent.run("PARENT SECRET: my deploy keeps failing")

        assert result.output == "Fixed: the disk was full."

        # child saw only its own system prompt and the task text
        for messages, _ in child.calls:
            text = str(messages)
            assert "PARENT SECRET" not in text
            assert "PARENT SYSTEM PROMPT" not in text
        assert child.calls[0][0][1]["content"] == "Find the error in big.log"

        # parent saw only the condensed answer, never the 52k-char file
        tool_msgs = [m for m in parent.last_messages if m["role"] == "tool"]
        assert tool_msgs[-1]["content"] == "The error is on line 1,204: disk full."
        assert "line of a very large file" not in str(parent.last_messages)

    def test_errors_reach_the_parent_as_text(self):
        runner = SubagentRunner(FakeLLMClient(), TOOLS)
        result = runner.as_tool().call({"task": "t", "tools": ["nope"]})
        assert "nope" in result.content
