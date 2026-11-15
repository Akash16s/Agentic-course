"""A provider outage, with and without the hardening. Free and offline.

    python chapters/ch13_hardening/examples/01_chaos.py
"""

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib import errors
from agentlib.hardening import (
    CachedClient,
    CircuitBreaker,
    CircuitOpen,
    RateLimiter,
    ResponseCache,
)
from agentlib.llm import LLMResponse, Usage
from agentlib.retry import chat_with_retry

TIMEOUT_S = 0.04      # what one failing request costs when nothing protects you
HEALTHY_S = 0.004     # normal latency, so 100 requests span a real window


class ChaosClient:
    """A provider that is down for a WINDOW OF TIME.

    Time-based, not call-based, deliberately. An outage lasts as long as it
    lasts regardless of how many requests you send at it — and a call-based
    model would unfairly punish the breaker, which is the thing that sends
    fewer requests.
    """

    def __init__(self, down_from=0.20, down_to=60.0):
        self.down_from = down_from
        self.down_to = down_to
        self.calls = 0
        self.started = time.monotonic()
        self.model = "chaos/model"

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.down_from <= time.monotonic() - self.started < self.down_to:
            time.sleep(TIMEOUT_S)          # a real outage is SLOW, not fast
            raise errors.ServerError("503 upstream unavailable")
        time.sleep(HEALTHY_S)
        return LLMResponse(text="ok", usage=Usage(100, 20), model=self.model)


MESSAGES = [{"role": "user", "content": "hello"}]
DURATION_S = 1.4          # every strategy experiences the SAME outage window
INTERVAL_S = 0.01         # a request every 10ms


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * p), len(ordered) - 1)]


def run(label, *, use_retry=False, use_breaker=False, reset_timeout_s=0.2):
    """Send requests at a fixed rate for a fixed TIME.

    Fixed duration, not a fixed count: a strategy that fails fast would
    otherwise finish before the outage ended, and the comparison would measure
    the harness rather than the strategy. That mistake flatters circuit
    breakers enormously and it is easy to make.
    """
    client = ChaosClient()
    breaker = (CircuitBreaker(failure_threshold=5, reset_timeout_s=reset_timeout_s)
               if use_breaker else None)
    succeeded = failed = rejected_fast = 0
    latencies: list[float] = []
    started = time.monotonic()
    next_send = started

    while time.monotonic() - started < DURATION_S:
        now = time.monotonic()
        if now < next_send:
            time.sleep(min(next_send - now, 0.002))
            continue
        next_send = max(next_send + INTERVAL_S, now)
        call_started = time.monotonic()
        try:
            if breaker is not None and use_retry:
                breaker.call(lambda: chat_with_retry(
                    client, MESSAGES, max_attempts=2, base_delay=0.001))
            elif breaker is not None:
                breaker.call(lambda: client.chat(MESSAGES))
            elif use_retry:
                chat_with_retry(client, MESSAGES, max_attempts=2, base_delay=0.001)
            else:
                client.chat(MESSAGES)
            succeeded += 1
        except CircuitOpen:
            rejected_fast += 1
        except errors.LLMError:
            failed += 1
        latencies.append((time.monotonic() - call_started) * 1000)

    print(f"  {label:<28} ok={succeeded:>4}  slow-fail={failed:>3}  "
          f"fast-reject={rejected_fast:>4}  upstream={client.calls:>4}  "
          f"p50={percentile(latencies, 0.50):>5.1f}ms  "
          f"p99={percentile(latencies, 0.99):>5.1f}ms")


print("=" * 100)
print(f"requests at {1/INTERVAL_S:.0f}/s for {DURATION_S}s; "
      f"the provider goes down at 0.20s and STAYS down")
print("=" * 100)
run("nothing")
run("retry only",               use_retry=True)
run("breaker",                  use_breaker=True, reset_timeout_s=0.3)
run("retry + breaker",          use_retry=True, use_breaker=True,
    reset_timeout_s=0.3)
print("""
Read it honestly, because the result is more interesting than the slogan.

  LOOK AT p50. Without a breaker it is the full timeout: during a sustained
  outage, the TYPICAL request is a slow failure. In a real service that is a
  worker held hostage, a connection held open, and a queue growing behind it —
  which is precisely how someone else's outage becomes your outage. The
  breaker turns those into instant rejections and p50 goes to zero.

  Look at p99 on the `retry only` row too: retry DOUBLES your worst-case
  latency during an outage, because every request now waits out two timeouts
  instead of one. Retry is for blips.

  UPSTREAM CALLS is the other win, and it is the polite one: far less traffic
  aimed at a service that is already struggling.

  BUT `fast-reject` IS NOT FREE. This outage never ends, so every rejection was
  going to fail anyway. In a SHORTER outage a large share of those rejections
  would have been requests that recovery had already fixed — an open breaker
  sheds load indiscriminately, and it keeps doing so for `reset_timeout_s`
  after the provider is healthy again.

  That dial is the whole tuning problem: too long and you reject healthy
  traffic long after recovery; too short and you hammer a service still on its
  knees. No setting is right for every outage, which is why you put the
  breaker's state in your metrics and look at it. Change `down_to` in this
  file to 0.8 and re-run to see the other side of that trade.

  RETRY ALONE recovers more requests than nothing at all — it is genuinely
  useful for blips. What it cannot do is notice that the blip has become an
  outage, and during one it doubles your traffic and your latency.

  The combination is the answer: retry absorbs the blips, the breaker notices
  when it has stopped being one. Neither is a substitute for the other, and
  neither is free.""")

print("\n" + "=" * 84)
print("CACHING: where it actually pays")
print("=" * 84)

rng = random.Random(3)
for label, unique in [("eval suite (re-run, all repeats)", 1),
                      ("agent re-asking sub-questions", 20),
                      ("real user traffic", 95)]:
    client = ChaosClient(down_from=10**6, down_to=10**6)
    cached = CachedClient(client, ResponseCache())
    for _ in range(100):
        question = f"question {rng.randrange(unique)}"
        cached.chat([{"role": "user", "content": question}])
    print(f"  {label:<34} hit rate {cached.cache.hit_rate:>5.0%}   "
          f"upstream calls {client.calls:>3}/100")
print("""
  Those figures are synthetic — real user traffic repeats far less than a
  uniform draw over 95 questions does, so treat the last row as an optimistic
  ceiling rather than a forecast. The point stands: your production hit rate
  will be low and your EVAL hit rate will be near total, and since Chapter 10
  has you running the suite on every change, that is where the cache pays.""")

print("\n" + "=" * 84)
print("RATE LIMITING: a bucket, not a fixed window")
print("=" * 84)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


clock = Clock()
limiter = RateLimiter(rate=5, capacity=10, clock=clock)
granted = [limiter.try_acquire() for _ in range(15)]
print(f"  at t=0  : {sum(granted)} of 15 granted   <- the burst, up to capacity")
clock.now = 1.0
print(f"  at t=1s : {limiter.tokens:.0f} tokens back  <- then the sustained rate")
print("""
  A strict "5 per second" limiter would have serialised that burst over three
  seconds, for no reason — the provider would happily have taken all ten at once.
  The bucket models what their limits actually are.""")
