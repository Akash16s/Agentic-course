"""SOLUTION — Chapter 17, Exercise 4."""

from __future__ import annotations

from typing import Any

from agentlib.conversation import Conversation
from agentlib.tools import ToolRegistry, parse_tool_calls, tool_result_message

from .exercise_1_reducers import END, add, append
from .exercise_2_graph import StateGraph


def build_agent_graph(client: Any, registry: ToolRegistry, *,
                      system: str | None = None) -> Any:
    specs = registry.specs() or None

    def think(state: dict[str, Any]) -> dict[str, Any]:
        response = client.chat(state["messages"], tools=specs)
        return {
            "messages": [response.as_message()],
            "steps": 1,
            "output": response.text,
            # replace, not append: these are THIS turn's requests, not a history
            "calls": parse_tool_calls(response),
        }

    def act(state: dict[str, Any]) -> dict[str, Any]:
        messages = [
            tool_result_message(call, registry.execute(call.name, call.arguments))
            for call in state.get("calls") or []
        ]
        return {"messages": messages}

    def route(state: dict[str, Any]) -> str:
        return "act" if state.get("calls") else "done"

    graph = StateGraph({"messages": append, "steps": add})
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.set_entry("think")
    graph.add_conditional_edges("think", route, {"act": "act", "done": END})
    graph.add_edge("act", "think")
    return graph.compile()


def seed_state(task: str, *, system: str | None = None) -> dict[str, Any]:
    """The initial state: history, counters, and an empty answer."""
    return {
        "messages": Conversation(system).add_user(task).messages,
        "steps": 0,
        "output": "",
        "calls": [],
    }
