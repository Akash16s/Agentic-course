"""What routing and cascades actually save, priced. Free and offline.

    python chapters/ch13b_routing/examples/01_cascade_maths.py

Prices come from agentlib/pricing.py, which is a SNAPSHOT. Run Chapter 1's
00_check_setup.py for live numbers and edit the table if they have moved.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.pricing import PRICES, cost_usd
from agentlib.routing import (
    break_even_accept_rate,
    expected_cost,
    expected_cost_chain,
    savings_vs_strong,
)

IN_TOKENS, OUT_TOKENS = 1_500, 400          # one typical agent step

CHEAP = "openai/gpt-5-nano"
MID = "openai/gpt-5-mini"
STRONG = "anthropic/claude-sonnet-4.5"


def per_call(model: str) -> float:
    return cost_usd(model, IN_TOKENS, OUT_TOKENS)


# ------------------------------------------------------------- price spread
print("=" * 78)
print(f"1. THE PRICE SPREAD  (one call: {IN_TOKENS:,} tokens in, {OUT_TOKENS} out)")
print("=" * 78)
rows = sorted(((per_call(m), m) for m in PRICES), reverse=True)
cheapest = rows[-1][0]
for cost, model in rows:
    print(f"  {model:<38} ${cost:.6f}   {cost / cheapest:>6.1f}x the cheapest")
print(f"""
  The dearest model in this table costs {rows[0][0] / cheapest:.0f}x the cheapest for the
  SAME request. Sending "what's the capital of France?" to the top row is not
  a quality decision; it is a donation.""")

# ----------------------------------------------------------- 2-tier cascade
c_cheap, c_strong = per_call(CHEAP), per_call(STRONG)
print("\n" + "=" * 78)
print(f"2. A CASCADE: {CHEAP} first, then {STRONG}")
print("=" * 78)
print(f"  cheap  ${c_cheap:.6f}/call      strong ${c_strong:.6f}/call      "
      f"ratio {c_strong / c_cheap:.0f}x\n")
print(f"  {'cheap accepted':>15} {'expected $/call':>16} {'vs strong-only':>15}")
for p in (0.0, 0.02, 0.10, 0.30, 0.50, 0.70, 0.90):
    e = expected_cost(p, c_cheap, c_strong)
    print(f"  {p:>15.0%} {e:>16.6f} {savings_vs_strong(p, c_cheap, c_strong):>+14.0%}")
be = break_even_accept_rate(c_cheap, c_strong)
print(f"""
  Break-even accept rate: {be:.1%}. If the cheap model's answer passes your check
  more often than that, the cascade is cheaper than always using strong.

  With a {c_strong / c_cheap:.0f}x price gap that bar is on the floor. On COST alone the
  cascade nearly always wins. Where it loses is everywhere else — see 4 and 5.""")

# ------------------------------------------- when the cheap tier isn't cheap
print("\n" + "=" * 78)
print("3. WHEN THE 'CHEAP' TIER ISN'T CHEAP ENOUGH")
print("=" * 78)
for cheap, strong in [(CHEAP, STRONG), (MID, STRONG),
                      ("anthropic/claude-haiku-4.5", STRONG),
                      ("openai/gpt-4o-mini", "openai/gpt-4o")]:
    cc, cs = per_call(cheap), per_call(strong)
    be = break_even_accept_rate(cc, cs)
    print(f"  {cheap:<28} -> {strong:<28} break-even {be:>5.1%}")
print("""
  Haiku -> Sonnet is a 3x gap, so the cheap tier must pass a THIRD of the time
  just to break even. Point that cascade at traffic that is mostly hard (say a
  25% accept rate) and it costs MORE than Sonnet alone, and it is slower too.
  A cascade wants a big price gap and traffic that is mostly easy.""")

# ----------------------------------------------------------------- latency
print("\n" + "=" * 78)
print("4. THE SAME MATHS IN SECONDS: CASCADES ARE SLOW ON EXACTLY THE HARD CASES")
print("=" * 78)
t_cheap, t_strong = 0.8, 3.0
print(f"  cheap ~{t_cheap}s, strong ~{t_strong}s (illustrative)\n")
print(f"  {'cheap accepted':>15} {'mean latency':>13} {'escalated request':>18}")
for p in (0.3, 0.5, 0.7, 0.9):
    mean = expected_cost(p, t_cheap, t_strong)        # same formula, seconds
    print(f"  {p:>15.0%} {mean:>12.2f}s {t_cheap + t_strong:>17.1f}s")
print(f"""
  The MEAN looks great. But every escalated request takes {t_cheap + t_strong:.1f}s, slower
  than strong-only's {t_strong}s — and the escalated ones are the hard ones, the
  ones where the user is already waiting for something careful. If you have a
  latency SLA on p95, check the escalated path against it, not the mean.""")

# ------------------------------------------------------------------ 3 tiers
print("\n" + "=" * 78)
print("5. THREE TIERS")
print("=" * 78)
costs = [per_call(CHEAP), per_call(MID), per_call(STRONG)]
for p_nano in (0.6, 0.2):
    two = expected_cost(p_nano, costs[0], costs[2])
    print(f"  nano passes {p_nano:.0%}, no middle tier"
          f"{'':<20}->  ${two:.6f}/call  ({1 - two / costs[-1]:+.0%} vs strong-only)")
    for p_mini in (0.6, 0.2):
        e = expected_cost_chain(costs, [p_nano, p_mini])
        print(f"  nano passes {p_nano:.0%}, mini passes {p_mini:.0%} of the rest"
              f"{'':<6}->  ${e:.6f}/call  ({1 - e / costs[-1]:+.0%} vs strong-only)")
print("""
  Each extra tier is one more call that is pure overhead whenever it fails.
  Look at the first block: a middle tier that passes only 20% of what reaches
  it buys three points of savings (+58% -> +61%), and in exchange EVERY hard
  request now makes three round trips instead of two. A middle tier pays off
  only when it passes a lot of what reaches it. Two tiers is the right
  default; earn the third with data.

  None of these numbers matter if your accept check is wrong. A check that
  passes bad answers makes the cascade look cheap and quietly ships mistakes.
  Measure the check itself on labelled data (Chapter 10) before trusting it.""")
