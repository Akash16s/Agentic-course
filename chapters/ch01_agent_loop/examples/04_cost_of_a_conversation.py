"""The quadratic cost trap, measured rather than asserted.

Simulates a 20-turn conversation WITHOUT calling the API, so it is free and instant.
It shows you why turn 20 costs 20x turn 1.

    python chapters/ch01_agent_loop/examples/04_cost_of_a_conversation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.pricing import cost_usd

MODEL = "anthropic/claude-sonnet-4.5"
TOKENS_PER_USER_MSG = 200
TOKENS_PER_REPLY = 300
TURNS = 20

history_tokens = 50  # a small system prompt
cumulative_input = 0
cumulative_output = 0
running_cost = 0.0

print(f"model: {MODEL}   ({TURNS} turns)\n")
print(f"{'turn':>4} {'input tok':>10} {'out tok':>8} {'turn $':>10} {'total $':>10}")
print("-" * 46)

for turn in range(1, TURNS + 1):
    history_tokens += TOKENS_PER_USER_MSG        # user speaks
    call_input = history_tokens                  # we resend EVERYTHING
    call_output = TOKENS_PER_REPLY

    turn_cost = cost_usd(MODEL, call_input, call_output)
    running_cost += turn_cost
    cumulative_input += call_input
    cumulative_output += call_output
    history_tokens += TOKENS_PER_REPLY           # the reply joins the history too

    if turn <= 3 or turn % 5 == 0 or turn == TURNS:
        print(f"{turn:>4} {call_input:>10,} {call_output:>8,} "
              f"{turn_cost:>10.4f} {running_cost:>10.4f}")

naive = cost_usd(MODEL, TOKENS_PER_USER_MSG * TURNS, TOKENS_PER_REPLY * TURNS)

print("-" * 46)
print(f"\ninput tokens actually sent : {cumulative_input:,}")
print(f"input tokens you'd guess   : {TOKENS_PER_USER_MSG * TURNS:,}")
print(f"\nreal cost   : ${running_cost:.4f}")
print(f"naive guess : ${naive:.4f}")
print(f"ratio       : {running_cost / naive:.1f}x\n")
print(f"At 10,000 conversations/day that is ${running_cost * 10_000:,.0f}/day.")
print("\nThis single effect is why Chapters 4, 5 and 13 exist.")
print("Try: change TURNS to 50 and watch the ratio.")
