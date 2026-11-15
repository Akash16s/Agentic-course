"""EXERCISE 5 — The cost-quality frontier, measured on real models.

No automated test. Needs your key; budget ~$0.20-0.50 for the whole exercise.

    python chapters/ch13b_routing/exercises/exercise_5_frontier.py

Run Chapter 1's 00_check_setup.py first and pick two models that are actually
listed today: one CHEAP (e.g. openai/gpt-5-nano, a small Llama/Qwen) and one
STRONG (e.g. anthropic/claude-sonnet-4.5). Model ids change. Put them in
CHEAP_MODEL / STRONG_MODEL below, and check both are in agentlib/pricing.py, or
your cost column will show the pessimistic fallback price.

TASKS
  1. Build a tiny eval set: 20 cases as agentlib.evals.core.EvalCase, with a
     checkable `expected`. Make it a deliberate MIX:
       - 12 easy  (capital cities, unit conversions, "reply with the word X",
                   extract the date from a sentence)
       - 8 hard   (multi-step arithmetic word problems, "what does this 15-line
                   function return for input 7", a logic puzzle)
     Tag each case "easy" or "hard" so you can check the ROUTER's accuracy too.
     Use a check you trust: expected_contains() or equals_expected() from
     agentlib.evals.core. A judge (Chapter 11) is fine but costs more.

  2. Run the set through FOUR strategies with EvalRunner, and record pass rate,
     total cost and p50 latency for each:
       a. strong-only   LLMClient(STRONG_MODEL)
       b. cheap-only    LLMClient(CHEAP_MODEL)
       c. router        RoutedClient(HeuristicRouter(), {EASY: cheap, HARD: strong})
                        (then again with LLMRouter(cheap) — and include the
                         router's own usage in the cost: LLMRouter.total_usage)
       d. cascade       Cascade([(cheap), (strong)], accept=...)
                        `accept` cannot see `expected` (that would be cheating:
                        in production you don't have it). Use a FORMAT check:
                        "the reply is a single number", "the reply is one word".
     `run_case` must return something with a `.cost` attribute for the report's
     cost column to be filled (CascadeResult has total_cost — wrap it).

  3. Print one table:

        strategy        pass   cost      $/correct   p50
        strong-only     19/20  $0.0410   $0.0022     1.9s
        cheap-only      13/20  $0.0019   $0.0001     0.7s
        ...

     Then answer, in a comment at the bottom of this file:
       - Which strategies are ON the frontier (no other strategy is both cheaper
         AND at least as good)? Which are dominated?
       - What was the cheap model's ACTUAL accept rate in the cascade? Compare it
         with break_even_accept_rate() for your two models. Did the cascade win?
       - How often did the HeuristicRouter send an "easy"-tagged case to HARD,
         and a "hard" case to EASY? Which of those two mistakes cost you a
         wrong answer, and which only cost money?

  4. Fallback, for real: build a FallbackClient whose FIRST entry is
     LLMClient("not-a-real/model-id"). What happens? (It should raise
     immediately — a 400/404 is non-retryable. If it silently fell through to
     the second model, you would never notice the typo in production.) Now try
     OpenRouter's own fallback instead:
         client.chat(msgs, extra_body={"models": [STRONG_MODEL, CHEAP_MODEL]})
     and print response.model. Which model answered? Is it the one you billed
     for in your CostTracker?

  5. Stretch: re-run step 2 a week later without changing anything. If any
     number moved by more than noise, a provider changed something under you.
     That is what pinning and a saved baseline are for. Compare case by case
     with Chapter 11's compare_runs, not by headline pass rate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

CHEAP_MODEL = "openai/gpt-5-nano"            # check these are still listed!
STRONG_MODEL = "anthropic/claude-sonnet-4.5"


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
