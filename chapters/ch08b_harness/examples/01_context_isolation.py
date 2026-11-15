"""What a subagent actually saves — and when it costs you instead. Free and offline.

A parent agent has to investigate three big log files, then keep working (eight more
steps of writing a fix). We run it twice with scripted fake models:

    DIRECT     the parent reads all three logs itself
    DELEGATED  the parent hands each log to a subagent and gets three lines back

Then we do it again with TINY files, where the answer flips.

    python chapters/ch08b_harness/examples/01_context_isolation.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.agent import Agent
from agentlib.harness import SubagentRunner
from agentlib.pricing import cost_usd
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tokens import estimate_messages_tokens, estimate_tokens
from agentlib.tools import ToolRegistry, tool

MODEL = "anthropic/claude-sonnet-4.5"
LOGS = ["auth.log", "billing.log", "search.log"]
SUMMARY = "Root cause: connection pool exhausted at 14:02; 312 timeouts; fix = raise pool to 50."


def run_scenario(file_chars: int, follow_up_steps: int) -> dict:
    @tool
    def read_file(path: str) -> str:
        """Read a file."""
        return ("2026-11-15 14:02:11 WARN pool wait 3001ms request=/api/x\n"
                * (file_chars // 58 + 1))[:file_chars]

    @tool
    def edit_code(change: str) -> str:
        """Make a small code change."""
        return "ok, edited"

    tools = ToolRegistry([read_file, edit_code])
    follow_ups = [tool_response(tool_call("edit_code", {"change": f"step {i}"}))
                  for i in range(follow_up_steps)]

    # --- DIRECT: the parent reads every log into its own window -------------------
    direct = FakeLLMClient(
        [tool_response(tool_call("read_file", {"path": p})) for p in LOGS]
        + follow_ups + ["Fixed."]
    )
    Agent(direct, tools=tools, max_steps=30).run("Find out why checkout is slow and fix it.")

    # --- DELEGATED: each log is read in a child's fresh conversation ---------------
    child = FakeLLMClient(
        [x for _ in LOGS for x in (tool_response(tool_call("read_file", {"path": "?"})),
                                   SUMMARY)]
    )
    runner = SubagentRunner(child, ToolRegistry([read_file]))
    parent = FakeLLMClient(
        [tool_response(tool_call("delegate", {"task": f"Read {p} and report the root cause "
                                              "of slow checkouts in 2 lines."}))
         for p in LOGS]
        + follow_ups + ["Fixed."]
    )
    Agent(parent, tools=ToolRegistry([edit_code, runner.as_tool()]), max_steps=30).run(
        "Find out why checkout is slow and fix it."
    )

    return {"direct": measure(direct), "parent": measure(parent), "children": measure(child)}


def measure(client: FakeLLMClient) -> dict:
    """Prompt tokens of every request this fake received: messages + tool schemas."""
    sizes = [
        estimate_messages_tokens(messages) + estimate_tokens(json.dumps(kw.get("tools") or []))
        for messages, kw in client.calls
    ]
    return {"calls": len(sizes), "peak": max(sizes), "total": sum(sizes)}


def report(title: str, file_chars: int, follow_up_steps: int) -> None:
    r = run_scenario(file_chars, follow_up_steps)
    d, p, c = r["direct"], r["parent"], r["children"]
    delegated_total = p["total"] + c["total"]
    print("=" * 74)
    print(f"{title}: 3 files of {file_chars:,} chars (~{file_chars // 4:,} tokens each), "
          f"then {follow_up_steps} more steps")
    print("=" * 74)
    print(f"{'':<28}{'calls':>7}{'peak ctx':>12}{'total in':>12}{'$ in':>10}")
    print("-" * 69)

    def row(name, calls, peak, total):
        print(f"{name:<28}{calls:>7}{peak:>12,}{total:>12,}{cost_usd(MODEL, total, 0):>10.4f}")

    row("DIRECT (one agent)", d["calls"], d["peak"], d["total"])
    row("DELEGATED  parent", p["calls"], p["peak"], p["total"])
    row("           3 subagents", c["calls"], c["peak"], c["total"])
    row("           TOTAL", p["calls"] + c["calls"], max(p["peak"], c["peak"]), delegated_total)
    ratio = delegated_total / d["total"]
    print(f"\n  parent's peak context: {d['peak']:,} -> {p['peak']:,} tokens "
          f"({d['peak'] / p['peak']:.1f}x smaller)")
    print(f"  total input tokens   : {ratio:.2f}x the direct run "
          f"({'cheaper' if ratio < 1 else 'MORE expensive'})\n")


report("BIG FILES", 24_000, follow_up_steps=8)
print("""  Why delegation won: in the DIRECT run each log is paid for on EVERY later
  call. Log 1 is re-sent 11 times. In the DELEGATED run each log is paid for twice
  (once to read, once more on the child's final call) and then it is gone; the
  parent carries three short summaries instead. The more steps the parent takes
  AFTER the reading, the bigger this win gets.
""")

report("TINY FILES", 400, follow_up_steps=1)
print("""  Why delegation lost: there was nothing big to isolate. Each subagent pays for
  its own system prompt, tool schemas and two calls, and the parent still pays for
  the delegate call and the summary. That is pure overhead.

  Rule of thumb: delegate when the child will read a lot and report a little.
  Two numbers to check: (tokens the child reads) and (steps the parent takes after).
  If both are small, do it inline.

  The cost you cannot see in this table: the parent only has the summary. If it
  later needs a detail the child left out, it must delegate AGAIN, or guess.
  Write delegation prompts that say exactly what to report back.""")
