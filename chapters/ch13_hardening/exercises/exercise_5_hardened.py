"""EXERCISE 5 — A hardened client, chaos-tested.

No automated test. Mostly offline; the last part needs your key.

    python chapters/ch13_hardening/exercises/exercise_5_hardened.py

TASKS
  1. Compose a `HardenedClient` that stacks, IN THIS ORDER (and justify the order
     to yourself before you write it):
        RateLimiter  -> CircuitBreaker -> CachedClient -> retry -> LLMClient
     Questions the order answers:
       - should a CACHE HIT consume a rate-limit permit? (no)
       - should a cache hit be blocked by an OPEN breaker? (no)
       - should retries count as separate breaker failures? (think about it —
         there is a defensible answer either way, pick one and say why)

  2. Build a `ChaosClient` that wraps FakeLLMClient and fails on demand:
        - fail_rate: raise ServerError with probability p
        - latency_s: sleep before responding
        - outage_after / outage_for: fail every call in a window
     Everything in this exercise runs against ChaosClient, offline and free.

  3. CHAOS TESTS — run 200 requests through HardenedClient and measure:
       a. fail_rate=0.3. How many requests succeed end to end? Compare with the
          retry layer removed.
       b. A 30-second outage in the middle. Plot (or just print) latency per
          request. Without the breaker, how long does each failing request take?
          With it?
       c. 50% duplicate requests. Measure the cache hit rate and the cost saved.
       d. Set the rate limiter to 2/s and fire 50 requests at once. Confirm no
          429s and that total time is ~25s.
       e. Set a BudgetGuard of $0.01 and let an agent loop. Confirm it stops, and
          compare where it stops against a post-hoc CostTracker with the same
          limit. Which one spent more?

  4. Then ONE test against the real API:
       a. Measure latency and cost for 5 identical requests with and without
          `mark_cacheable_prefix` on a long system prompt (2,000+ tokens).
       b. Now add `datetime.now()` to the system prompt and measure again. That
          difference is the mistake in section 7 of the chapter, priced.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
