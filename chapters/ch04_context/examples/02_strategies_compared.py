"""Four context strategies on the same 40-turn conversation. Free and offline.

    python chapters/ch04_context/examples/02_strategies_compared.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.context import (
    ContextBudget,
    compact,
    trim_messages,
    truncate_tool_results,
)
from agentlib.tokens import estimate_messages_tokens

# a realistic agent transcript: a task, then 20 rounds of tool use
conversation = [{"role": "user", "content":
                 "Audit every config file in the repo and list the ones missing a timeout."}]
for i in range(20):
    conversation.append({
        "role": "assistant", "content": None,
        "tool_calls": [{"id": f"c{i}", "type": "function",
                        "function": {"name": "read_file",
                                     "arguments": f'{{"path": "svc{i}/config.yaml"}}'}}],
    })
    conversation.append({
        "role": "tool", "tool_call_id": f"c{i}", "name": "read_file",
        "content": f"# svc{i}/config.yaml\n" + ("key: value\n" * 300),  # a big file
    })

budget = ContextBudget(context_window=16_000, reserve_output=2_000, system_tokens=300)
original = estimate_messages_tokens(conversation)


def summarise(transcript: str) -> str:
    return ("Auditing config files for missing timeouts. Read svc0-svc13 so far; "
            "svc3 and svc9 have no timeout key. Remaining: svc14-svc19.")


strategies = {
    "none (what the loop does)": conversation,
    "truncate tool results":     truncate_tool_results(conversation, max_chars=400),
    "sliding window":            trim_messages(conversation, budget.available_for_history,
                                               keep_first=1, keep_last=4),
    "compact":                   compact(conversation, summarise, keep_recent=4),
    "truncate + compact":        compact(
        truncate_tool_results(conversation, max_chars=400), summarise, keep_recent=4),
}

print(f"context window {budget.context_window:,} | available for history "
      f"{budget.available_for_history:,}\n")
print(f"{'strategy':<28} {'msgs':>5} {'tokens':>9} {'of budget':>10}  fits")
print("-" * 68)
for label, messages in strategies.items():
    tokens = estimate_messages_tokens(messages)
    pct = tokens / budget.available_for_history * 100
    print(f"{label:<28} {len(messages):>5} {tokens:>9,} {pct:>9.0f}%  "
          f"{'yes' if budget.fits(messages) else 'NO'}")

print("-" * 68)
print(f"""
The unmanaged conversation is {original:,} tokens — {original / budget.available_for_history:.1f}x over the budget.

Order of operations matters, and it is the cheap-to-expensive order:

  1. truncate tool results   free, lossless-ish, do it always
  2. compact                 costs one cheap model call, keeps the plot
  3. trim                    free, but loses information permanently

Note what "sliding window" alone costs you here: with keep_first=1 the task statement
survives, but everything the agent learned in turns 2-16 is simply gone. Compaction
keeps it, for the price of one call to a small model.""")
