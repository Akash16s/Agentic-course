"""The same agent as a loop and as a graph. Free and offline.

    python chapters/ch17_frameworks/examples/01_loop_vs_graph.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.agent import Agent
from agentlib.conversation import Conversation
from agentlib.graph import END, GraphError, StateGraph, add, append
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, parse_tool_calls, tool, tool_result_message


@tool
def lookup(topic: str) -> str:
    """Look something up."""
    return f"facts about {topic}"


REG = ToolRegistry([lookup])


def script():
    return FakeLLMClient([
        tool_response(tool_call("lookup", {"topic": "postgres"})),
        tool_response(tool_call("lookup", {"topic": "redis"})),
        "Postgres for storage, Redis for cache.",
    ])


print("=" * 76)
print("A: the Chapter 3 loop")
print("=" * 76)
result = Agent(script(), tools=REG, system="be brief").run("compare them")
print(f"  output : {result.output}")
print(f"  tools  : {result.tool_sequence}")
print(f"  steps  : {result.step_count}")

print("\n" + "=" * 76)
print("B: the same thing as a graph")
print("=" * 76)

client = script()


def think(state):
    response = client.chat(state["messages"], tools=REG.specs())
    return {"messages": [response.as_message()], "steps": 1,
            "output": response.text, "calls": parse_tool_calls(response)}


def act(state):
    return {"messages": [
        tool_result_message(c, REG.execute(c.name, c.arguments))
        for c in state["calls"]
    ]}


graph = StateGraph({"messages": append, "steps": add})
graph.add_node("think", think)
graph.add_node("act", act)
graph.set_entry("think")
graph.add_conditional_edges("think", lambda s: "act" if s["calls"] else "done",
                            {"act": "act", "done": END})
graph.add_edge("act", "think")
compiled = graph.compile()

state = {"messages": Conversation("be brief").add_user("compare them").messages,
         "steps": 0, "output": "", "calls": []}
graph_result = compiled.invoke(state)
print(f"  output : {graph_result.state['output']}")
print(f"  path   : {graph_result.path}")
print(f"  steps  : {graph_result.state['steps']}")

print("\n" + "=" * 76)
print("WHAT THE GRAPH BOUGHT YOU")
print("=" * 76)

print("\n1. YOU CAN DRAW IT")
print("   " + compiled.graph.to_mermaid().replace("\n", "\n   "))

print("\n2. YOU CAN VALIDATE IT AT BUILD TIME")
broken = StateGraph()
broken.add_node("think", think)
broken.add_node("summarise", act)          # nothing points out of it
broken.set_entry("think")
broken.add_edge("think", END)
try:
    broken.compile()
except GraphError as exc:
    print(f"   {exc}")
print("   -> in a hand-rolled loop that is a KeyError three steps in, or a")
print("      silent stall. Here it is a sentence naming the node.")

print("\n3. YOU GET STEP STREAMING FOR FREE")
client = script()
for step in compiled.stream(dict(state)):
    print(f"   {step.node:<7} steps={step.state['steps']} "
          f"messages={len(step.state['messages'])}")

print("\n4. THE STATE IS A PLAIN DICT — so it can be checkpointed (ch 15)")
print(f"   keys: {sorted(graph_result.state)}")

print("\n" + "=" * 76)
print("WHAT IT COST YOU")
print("=" * 76)
print("""  The loop body in Chapter 3 is about twelve lines. This is thirty, spread
  across two node functions, a router, a reducer map and an edge table. You
  also acquired a vocabulary (nodes, edges, reducers, compile) that a new
  reader has to learn before they can follow the control flow.

  And a graph is still a loop:""")
spin = StateGraph()
spin.add_node("spin", lambda s: {})
spin.set_entry("spin").add_edge("spin", "spin")
runaway = spin.compile().invoke({}, max_steps=20)
print(f"    a cycle with no exit ran {len(runaway.steps)} steps and "
      f"stopped_early={runaway.stopped_early}")
print("""    max_steps did that, not the diagram. Drawing a loop does not make
    it terminate.

  THE HONEST SUMMARY: you are buying a picture, compile-time validation,
  streaming and a checkpointable state object. If you need those four things —
  and a resumable human-in-the-loop workflow genuinely does — it is a good
  trade. For a straight-line agent with five tools it is not, and `while` is a
  perfectly respectable abstraction.""")
