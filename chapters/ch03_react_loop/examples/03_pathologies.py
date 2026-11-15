"""The four loop pathologies, each reproduced. Free and offline.

    python chapters/ch03_react_loop/examples/03_pathologies.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.agent import Agent
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool
from chapters.ch03_react_loop.solutions.exercise_2_stop import detect_repetition


@tool
def search(query: str) -> str:
    """Search the knowledge base."""
    return "no results found"          # <- the root cause of the repeater


@tool
def lookup(term: str) -> str:
    """Look a term up in the glossary."""
    return "see: search"               # <- the root cause of the ping-pong


REG = ToolRegistry([search, lookup])

cases = {
    "1. THE REPEATER\n   same tool, same args, forever.\n   Cause: a tool result with no\n   information in it.": (
        [tool_response(tool_call("search", {"query": "policy"}))] * 30
    ),
    "2. THE PING-PONG\n   A-B-A-B. Cause: two tools whose\n   descriptions overlap, or each\n   pointing at the other.": (
        [
            tool_response(tool_call("search", {"query": "x"})),
            tool_response(tool_call("lookup", {"term": "x"})),
        ] * 15
    ),
    "3. THE PREMATURE QUITTER\n   answers without working.\n   Cause: prompt describes tools\n   instead of requiring them.": (
        ["I would need to search the knowledge base to answer that."]
    ),
    "4. THE RAMBLER\n   always one more thing to check.\n   Cause: no completion criterion.": (
        [tool_response(tool_call("search", {"query": f"aspect {i}"})) for i in range(30)]
    ),
}

for label, script in cases.items():
    result = Agent(FakeLLMClient(script), tools=REG, max_steps=8).run("what is the policy?")
    sequence = result.tool_sequence
    shown = " -> ".join(sequence[:6]) + (" -> ..." if len(sequence) > 6 else "")
    print("=" * 72)
    print(label)
    print("-" * 72)
    print(f"  stop_reason        : {result.stop_reason.value}")
    print(f"  tool_sequence      : {shown or '(none)'}")
    print(f"  detect_repetition  : {detect_repetition(result.steps)}")
    print(f"  output             : {result.output[:60]!r}")
    print()

print("""Every one of these is visible in a single glance at `tool_sequence`.
That is what the trace is for, and why run() must not return a bare string.

Fixes, in order of how often they work:
  repeater   -> make the tool say something useful when it finds nothing
                ("no results for 'policy'; try broader terms, or list_topics()")
  ping-pong  -> rewrite the two descriptions so they do not overlap
  quitter    -> system prompt: "Use your tools. Never say you would need to."
  rambler    -> a submit_answer tool + a stated completion criterion""")
