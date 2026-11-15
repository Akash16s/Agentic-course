"""Tests for Chapter 3, Exercise 4 — the loop."""

import pytest

from agentlib import errors
from agentlib.conversation import Conversation
from agentlib.errors import StopSignal
from agentlib.llm import LLMResponse, Usage
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool
from chapters.ch03_react_loop.exercises.exercise_1_result import StopReason
from chapters.ch03_react_loop.exercises.exercise_4_agent import Agent


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def search(query: str) -> str:
    """Search for something."""
    return f"results for {query}"


@tool
def finish(answer: str) -> str:
    """Submit the final answer."""
    raise StopSignal(answer)


REG = ToolRegistry([add, search, finish])


class FakeClock:
    def __init__(self, step=0.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


class TestHappyPath:
    def test_no_tools_needed(self):
        agent = Agent(FakeLLMClient(["Paris."]))
        r = agent.run("capital of France?")
        assert r.output == "Paris."
        assert r.stop_reason == StopReason.DONE
        assert r.step_count == 1
        assert r.succeeded

    def test_one_tool_then_answer(self):
        client = FakeLLMClient(
            [tool_response(tool_call("add", {"a": 2, "b": 3})), "The answer is 5."]
        )
        r = Agent(client, tools=REG).run("2+3?")
        assert r.output == "The answer is 5."
        assert r.stop_reason == StopReason.DONE
        assert r.step_count == 2
        assert r.tool_sequence == ["add"]

    def test_multi_step(self):
        client = FakeLLMClient([
            tool_response(tool_call("search", {"query": "a"})),
            tool_response(tool_call("search", {"query": "b"})),
            tool_response(tool_call("add", {"a": 1, "b": 1})),
            "Done.",
        ])
        r = Agent(client, tools=REG, max_steps=10).run("go")
        assert r.tool_sequence == ["search", "search", "add"]
        assert r.step_count == 4

    def test_parallel_calls_in_one_step(self):
        client = FakeLLMClient([
            tool_response(
                tool_call("search", {"query": "a"}, call_id="c1"),
                tool_call("search", {"query": "b"}, call_id="c2"),
            ),
            "Done.",
        ])
        r = Agent(client, tools=REG).run("go")
        assert r.steps[0].tool_names == ["search", "search"]
        assert len(r.steps[0].tool_messages) == 2


class TestConversation:
    def test_message_order(self):
        client = FakeLLMClient(
            [tool_response(tool_call("add", {"a": 1, "b": 1})), "It is 2."]
        )
        r = Agent(client, tools=REG, system="be helpful").run("1+1?")
        roles = [m["role"] for m in r.conversation.messages]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]

    def test_assistant_message_keeps_its_tool_calls(self):
        client = FakeLLMClient(
            [tool_response(tool_call("add", {"a": 1, "b": 1})), "2"]
        )
        r = Agent(client, tools=REG).run("1+1?")
        assert r.conversation.messages[1].get("tool_calls"), (
            "dropping tool_calls makes the provider reject the follow-up"
        )

    def test_accepts_a_conversation_and_does_not_mutate_it(self):
        conv = Conversation("sys").add_user("hello")
        before = conv.messages
        r = Agent(FakeLLMClient(["hi"])).run(conv)
        assert conv.messages == before, "the caller's conversation must be untouched"
        assert len(r.conversation) > len(conv)

    def test_system_prompt_is_used_for_string_tasks(self):
        client = FakeLLMClient(["ok"])
        Agent(client, system="you are a pirate").run("hello")
        assert client.last_messages[0] == {"role": "system", "content": "you are a pirate"}


class TestStopping:
    def test_max_steps(self):
        client = FakeLLMClient([tool_response(tool_call("search", {"query": "x"}))] * 50)
        r = Agent(client, tools=REG, max_steps=4).run("go")
        assert r.stop_reason == StopReason.MAX_STEPS
        assert r.step_count == 4
        assert not r.succeeded

    def test_stop_tool(self):
        client = FakeLLMClient([tool_response(tool_call("finish", {"answer": "42"}))])
        r = Agent(client, tools=REG).run("go")
        assert r.stop_reason == StopReason.STOP_TOOL
        assert r.output == "42"
        assert r.succeeded

    def test_budget(self):
        client = FakeLLMClient(
            [tool_response(tool_call("search", {"query": "x"}))] * 50
        )
        r = Agent(client, tools=REG, budget_usd=1e-9, max_steps=50).run("go")
        assert r.stop_reason == StopReason.BUDGET
        assert r.cost > 0, "the money was spent; report it"
        assert r.error and "budget" in r.error.lower()

    def test_timeout(self):
        client = FakeLLMClient([tool_response(tool_call("search", {"query": "x"}))] * 50)
        r = Agent(
            client, tools=REG, max_steps=50, timeout_s=1.0, clock=FakeClock(step=0.4)
        ).run("go")
        assert r.stop_reason == StopReason.TIMEOUT

    def test_no_timeout_by_default(self):
        client = FakeLLMClient(["done"])
        r = Agent(client, clock=FakeClock(step=1000)).run("go")
        assert r.stop_reason == StopReason.DONE


class TestErrors:
    def test_run_never_raises_on_llm_failure(self):
        client = FakeLLMClient([errors.ServerError("503")] * 10)
        r = Agent(client, max_attempts=2).run("go")  # sleeps are real but tiny
        assert r.stop_reason == StopReason.ERROR
        assert r.error is not None
        assert not r.succeeded

    def test_partial_trace_survives_a_failure(self):
        client = FakeLLMClient([
            tool_response(tool_call("search", {"query": "a"})),
            errors.BadRequestError("400"),
        ])
        r = Agent(client, tools=REG).run("go")
        assert r.stop_reason == StopReason.ERROR
        assert r.step_count == 1, "keep what you gathered before the failure"
        assert r.tool_sequence == ["search"]

    def test_tool_failure_does_not_stop_the_loop(self):
        @tool
        def broken() -> str:
            """Always fails."""
            raise RuntimeError("nope")

        reg = ToolRegistry([broken])
        client = FakeLLMClient(
            [tool_response(tool_call("broken", {})), "I could not do that."]
        )
        r = Agent(client, tools=reg).run("go")
        assert r.stop_reason == StopReason.DONE
        assert "RuntimeError" in r.steps[0].tool_messages[0]["content"]

    def test_unknown_tool_does_not_stop_the_loop(self):
        client = FakeLLMClient(
            [tool_response(tool_call("imaginary", {})), "Let me use a real tool."]
        )
        r = Agent(client, tools=REG).run("go")
        assert r.stop_reason == StopReason.DONE


class TestAccounting:
    def test_usage_accumulates(self):
        client = FakeLLMClient(
            [tool_response(tool_call("add", {"a": 1, "b": 1})), "2"]
        )
        r = Agent(client, tools=REG).run("go")
        assert r.usage.prompt_tokens == 20  # 2 calls x default fake usage 10/5
        assert r.usage.completion_tokens == 10

    def test_cost_is_reported(self):
        r = Agent(FakeLLMClient(["hi"])).run("go")
        assert r.cost > 0

    def test_on_step_callback(self):
        seen = []
        client = FakeLLMClient(
            [tool_response(tool_call("add", {"a": 1, "b": 1})), "2"]
        )
        Agent(client, tools=REG, on_step=seen.append).run("go")
        assert [s.index for s in seen] == [0, 1]
        assert seen[0].tool_names == ["add"]

    def test_step_durations_recorded(self):
        r = Agent(FakeLLMClient(["hi"]), clock=FakeClock(step=0.5)).run("go")
        assert r.steps[0].duration_s > 0


class TestToolsArgument:
    def test_no_tools_means_tools_is_not_sent(self):
        client = FakeLLMClient(["hi"])
        Agent(client).run("go")
        _, kwargs = client.calls[0]
        assert kwargs.get("tools") is None, "an empty tools array is not the same as none"

    def test_specs_are_passed_when_tools_exist(self):
        client = FakeLLMClient(["hi"])
        Agent(client, tools=REG).run("go")
        _, kwargs = client.calls[0]
        assert kwargs["tools"] and len(kwargs["tools"]) == 3
