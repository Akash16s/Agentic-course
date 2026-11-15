"""Tests for Chapter 3, Exercise 1 — the trace objects."""

import pytest

from agentlib.llm import LLMResponse, Usage
from agentlib.tools import ToolCall
from chapters.ch03_react_loop.exercises.exercise_1_result import (
    AgentResult,
    Step,
    StopReason,
)


def step(index=0, names=(), text="hi"):
    return Step(
        index=index,
        response=LLMResponse(text=text),
        tool_calls=[ToolCall(id=f"c{i}", name=n) for i, n in enumerate(names)],
    )


class TestStopReason:
    def test_all_six_exist(self):
        assert {r.value for r in StopReason} == {
            "done", "max_steps", "budget", "timeout", "stop_tool", "error",
        }

    def test_compares_equal_to_its_string(self):
        # makes logging, JSON and test assertions painless
        assert StopReason.DONE == "done"

    def test_json_serialisable(self):
        import json

        assert json.dumps({"r": StopReason.BUDGET}) == '{"r": "budget"}'


class TestStep:
    def test_defaults(self):
        s = Step(index=0, response=LLMResponse(text="hi"))
        assert s.tool_calls == []
        assert s.tool_messages == []
        assert s.duration_s == 0.0

    def test_used_tools(self):
        assert not step().used_tools
        assert step(names=["a"]).used_tools

    def test_tool_names_in_order(self):
        assert step(names=["search", "read"]).tool_names == ["search", "read"]

    def test_defaults_are_not_shared(self):
        a = Step(index=0, response=LLMResponse(text="x"))
        b = Step(index=1, response=LLMResponse(text="y"))
        a.tool_calls.append(ToolCall(id="c", name="t"))
        assert b.tool_calls == [], "mutable default leaked between instances"


class TestAgentResult:
    def test_defaults(self):
        r = AgentResult(output="x", stop_reason=StopReason.DONE)
        assert r.steps == []
        assert r.conversation is None
        assert r.cost == 0.0
        assert r.error is None
        assert r.usage.total_tokens == 0

    def test_step_count(self):
        r = AgentResult("x", StopReason.DONE, steps=[step(), step(1)])
        assert r.step_count == 2

    @pytest.mark.parametrize("reason", [StopReason.DONE, StopReason.STOP_TOOL])
    def test_succeeded(self, reason):
        assert AgentResult("x", reason).succeeded

    @pytest.mark.parametrize(
        "reason",
        [StopReason.MAX_STEPS, StopReason.BUDGET, StopReason.TIMEOUT, StopReason.ERROR],
    )
    def test_failed(self, reason):
        # a cut-off agent produces confident-sounding partial answers; they are failures
        assert not AgentResult("plausible text", reason).succeeded

    def test_tool_sequence_flattens_across_steps(self):
        r = AgentResult(
            "x",
            StopReason.DONE,
            steps=[step(0, ["search", "read"]), step(1, ["write"]), step(2)],
        )
        assert r.tool_sequence == ["search", "read", "write"]

    def test_tool_sequence_empty_when_no_tools(self):
        assert AgentResult("x", StopReason.DONE, steps=[step()]).tool_sequence == []

    def test_repetition_is_visible_in_the_sequence(self):
        r = AgentResult("x", StopReason.MAX_STEPS,
                        steps=[step(i, ["search"]) for i in range(4)])
        assert r.tool_sequence == ["search"] * 4
