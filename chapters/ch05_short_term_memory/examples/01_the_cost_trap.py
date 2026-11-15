"""The summarisation cost trap, measured. Free and offline.

    python chapters/ch05_short_term_memory/examples/01_the_cost_trap.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.context import message_pairs
from agentlib.memory.short_term import FullHistory, SlidingWindow, SummaryBuffer
from agentlib.pricing import cost_usd
from agentlib.tokens import estimate_messages_tokens

CHAT_MODEL = "anthropic/claude-sonnet-4.5"
SUMMARY_MODEL = "openai/gpt-4o-mini"
TURNS = 40


class Summariser:
    """Counts calls and charges for them."""

    def __init__(self, model: str = SUMMARY_MODEL):
        self.model = model
        self.calls = 0
        self.cost = 0.0

    def __call__(self, transcript: str) -> str:
        self.calls += 1
        self.cost += cost_usd(self.model, len(transcript) // 4, 150)
        return "The user is planning a database migration. Decided on Postgres 16."


class NaiveSummaryBuffer(SummaryBuffer):
    """What people write first: re-summarise on every turn, no cache, no carry."""

    def build(self, messages):
        groups = message_pairs(messages)
        if len(groups) <= self.keep_recent:
            return list(messages)
        old = [m for g in groups[: -self.keep_recent] for m in g]
        recent = [m for g in groups[-self.keep_recent:] for m in g]
        transcript = "\n".join(str(m.get("content"))[:400] for m in old)
        return [{"role": "user", "content": self.summarise(transcript)}] + recent


def simulate(strategy) -> tuple[float, int, float]:
    """Walk a conversation turn by turn, billing every model call."""
    history, chat_cost = [], 0.0
    for turn in range(TURNS):
        history.append({"role": "user", "content": f"Question {turn}. " + "x" * 300})
        view = strategy.build(history)
        chat_cost += cost_usd(CHAT_MODEL, estimate_messages_tokens(view), 200)
        history.append({"role": "assistant", "content": f"Answer {turn}. " + "y" * 400})
    summariser = getattr(strategy, "summarise", None)
    extra = getattr(summariser, "cost", 0.0)
    calls = getattr(summariser, "calls", 0)
    return chat_cost, calls, extra


configs = {
    "FullHistory":              lambda: FullHistory(),
    "SlidingWindow(4k)":        lambda: SlidingWindow(max_tokens=4000),
    "naive, cheap summariser":  lambda: NaiveSummaryBuffer(Summariser(), max_tokens=4000,
                                                           keep_recent=4),
    "naive, SAME model":        lambda: NaiveSummaryBuffer(Summariser(CHAT_MODEL),
                                                           max_tokens=4000, keep_recent=4),
    "cached (ours)":            lambda: SummaryBuffer(Summariser(), max_tokens=4000,
                                                      keep_recent=4),
}

print(f"{TURNS}-turn conversation | chat={CHAT_MODEL} | summariser={SUMMARY_MODEL}\n")
print(f"{'strategy':<26} {'chat $':>9} {'sum calls':>10} {'sum $':>9} {'total $':>9}")
print("-" * 68)
for label, make in configs.items():
    chat, calls, extra = simulate(make())
    print(f"{label:<26} {chat:>9.4f} {calls:>10} {extra:>9.4f} {chat + extra:>9.4f}")

print("-" * 68)
print("""
READ THIS CAREFULLY, because the obvious conclusion is wrong.

The naive buffer with a CHEAP summariser wins on total cost. It compacts harder,
so the chat context stays smaller, and gpt-4o-mini is cheap enough that 38 calls
barely register. If cost were the only axis, naive would be fine.

Three things make it a trap anyway:

1. LOOK AT 'naive, SAME model'. Using your main model to summarise is the most
   common version of this mistake — it is one line of config, and nobody notices.
   Now the 38 calls cost real money and the ordering flips.

2. THE SUMMARISATION COST GROWS QUADRATICALLY. 40 turns hides it. Each call
   re-reads a longer transcript than the last, so doubling the conversation
   roughly quadruples this column. Try TURNS = 200.

3. IT LOSES INFORMATION. The naive version never carries the previous summary
   forward, so every compaction discards whatever the last one had folded away.
   By turn 40 the first ten turns are simply gone. That does not show up in any
   cost column, and it is the reason the cached version exists.

The honest summary: caching buys you bounded summarisation cost and preserved
early facts. It does NOT always buy you a smaller bill, and an example that
claimed otherwise would be lying to you.

Note too that FullHistory is not automatically worst — for a short conversation
it wins outright. These are trade-offs, not a ladder.""")
