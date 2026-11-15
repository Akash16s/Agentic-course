"""EXERCISE 4 — Port the Chapter 3 agent onto the graph.

The point of this exercise is the COMPARISON, not the code. When it passes, put
your graph version next to your Chapter 3 `Agent.run` and ask which you would
rather debug at 3am.

    pytest chapters/ch17_frameworks/tests -q -k port
"""

from __future__ import annotations

from typing import Any

from agentlib.conversation import Conversation
from agentlib.tools import ToolRegistry, parse_tool_calls, tool_result_message

from .exercise_1_reducers import END, add, append
from .exercise_2_graph import StateGraph


def build_agent_graph(client: Any, registry: ToolRegistry, *,
                      system: str | None = None) -> Any:
    """Build a compiled ReAct graph.

    STATE:
        messages: list   (reducer: append)
        steps:    int    (reducer: add)
        output:   str    (reducer: replace — the default)

    NODES:
      "think":
          call `client.chat(state["messages"], tools=registry.specs() or None)`
          return {"messages": [response.as_message()],
                  "steps": 1,
                  "output": response.text,
                  "calls": parse_tool_calls(response)}
          ("calls" uses the default replace reducer — it is this turn's requests,
           not an accumulating list)

      "act":
          for each call in state["calls"], run registry.execute and build a
          tool_result_message; return {"messages": [...those messages...]}

    EDGES:
        entry = "think"
        think -> conditional on whether state["calls"] is non-empty:
                     {"act": "act", "done": END}
        act   -> think

    SEED the state with the system prompt and the task, e.g. via
    `Conversation(system).add_user(task).messages`.

    Return `graph.compile()`.

    NOW COMPARE. Your Chapter 3 loop was about twelve lines of body. This is
    roughly thirty, spread across three functions and a mapping. In exchange you
    get: a diagram, compile-time validation, free step streaming, and a state
    object you could checkpoint between nodes (Chapter 15).

    Whether that trade is worth it depends entirely on whether you need those
    four things. For a straight-line agent it is not. For a resumable
    human-in-the-loop workflow it very much is. Being able to make that judgement
    is what this chapter is for.
    """
    # TODO: implement
    raise NotImplementedError


def seed_state(task: str, *, system: str | None = None) -> dict[str, Any]:
    """The initial state.

    Spec:
        {"messages": Conversation(system).add_user(task).messages,
         "steps": 0, "output": "", "calls": []}
    """
    # TODO: implement
    raise NotImplementedError
