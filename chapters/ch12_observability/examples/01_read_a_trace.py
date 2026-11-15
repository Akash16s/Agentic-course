"""Four bugs, found from the trace alone. Free and offline.

    python chapters/ch12_observability/examples/01_read_a_trace.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.agent import Agent
from agentlib.llm import LLMResponse, Usage
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool
from agentlib.tracing import TracedClient, TracedRegistry, Tracer


def big_response(prompt_tokens):
    return LLMResponse(text="", finish_reason="tool_calls",
                       tool_calls=[tool_call("read_file", {"path": "big.log"})],
                       usage=Usage(prompt_tokens, 40), model="anthropic/claude-sonnet-4.5")


@tool
def read_file(path: str) -> str:
    """Read a file."""
    return "x" * 40_000        # BUG 1: unbounded tool output


@tool
def search(query: str) -> str:
    """Search the web."""
    time.sleep(0.25)           # BUG 2: a slow tool
    return "no results"        # BUG 4: a useless result -> the repeater


@tool
def check_auth(token: str) -> str:
    """Validate a token."""
    raise ConnectionError("auth service unreachable")   # BUG 3


REG = ToolRegistry([read_file, search, check_auth])

tracer = Tracer(trace_id="demo")
client = TracedClient(FakeLLMClient([
    big_response(1_000),
    tool_response(tool_call("search", {"query": "deploy failure"})),
    tool_response(tool_call("check_auth", {"token": "abc"})),
    LLMResponse(text="", finish_reason="tool_calls",
                tool_calls=[tool_call("search", {"query": "deploy failure"})],
                usage=Usage(52_000, 30), model="anthropic/claude-sonnet-4.5"),
    "I could not determine the cause.",
]), tracer)

with tracer.span("agent.run", kind="agent", task="why did the deploy fail?") as root:
    result = Agent(client, tools=TracedRegistry(REG, tracer), max_steps=5).run(
        "why did the deploy fail?")
    root.set(steps=result.step_count, stop_reason=result.stop_reason.value)

print(tracer.render())
print()
print(tracer.summary())

print("\n" + "=" * 76)
print("NOW READ IT. Four bugs, none visible in the final answer.")
print("=" * 76)

slowest = tracer.slowest(3)
print("\n1. WHERE DID THE TIME GO?  tracer.slowest()")
for span in slowest:
    print(f"     {span.name:<22} {span.duration_s*1000:>7.0f}ms")
print("     -> tool.search owns nearly all of it. If you only traced LLM calls,")
print("        this agent would look like it spent the time 'thinking'.")

print("\n2. WHERE DID THE MONEY GO?  costs per llm.chat span")
llm_spans = [s for s in tracer.spans if s.kind == "llm"]
for span in llm_spans:
    print(f"     tokens in={span.attributes.get('prompt_tokens'):>6}  "
          f"${span.attributes.get('cost_usd', 0):.4f}")
costs = [s.attributes.get("cost_usd", 0.0) for s in llm_spans]
worst = max(range(len(costs)), key=lambda i: costs[i])
ratio = costs[worst] / max(min(c for c in costs if c > 0), 1e-9)
print(f"     -> call {worst + 1} cost {ratio:.0f}x the cheapest one. Look at the span")
print("        before it: read_file returned 40,000 characters straight into")
print("        the context. That is Chapter 4's unbounded tool output, priced.")

print("\n3. WHAT BROKE?  tracer.errors()")
for span in tracer.errors():
    print(f"     {span.name}: {span.error}")
print("     -> and the loop carried on, exactly as Chapter 2 wants. The model")
print("        saw the error and moved on. You would never know without this.")

print("\n4. WHAT DID IT ACTUALLY DO?  the tool sequence")
print(f"     {result.tool_sequence}")
print("     -> search appears twice with the same query, because the tool")
print("        returns 'no results' and gives the model nothing to work with.")
print("        That is the repeater from Chapter 3, and the fix is in the TOOL,")
print("        not the prompt.")

print("""
Not one of those four is visible in the final answer, which is a perfectly
polite "I could not determine the cause." An eval would tell you this case
failed. Only the trace tells you why — and that it failed four different ways.""")
