"""A fallback chain meeting 429s, 503s and a 400. Free and offline.

    python chapters/ch13b_routing/examples/02_fallback_in_action.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib import errors
from agentlib.hardening import CircuitBreaker
from agentlib.llm import LLMResponse, Usage
from agentlib.routing import AllModelsFailed, FallbackClient

MSGS = [{"role": "user", "content": "summarise this ticket"}]


class ScriptedClient:
    """A provider that does what `behaviour(call_number)` says.

    Return a string to answer, or an exception to raise.
    """

    def __init__(self, model, behaviour):
        self.model = model
        self.behaviour = behaviour
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        outcome = self.behaviour(self.calls)
        if isinstance(outcome, Exception):
            raise outcome
        return LLMResponse(text=outcome, usage=Usage(500, 100), model=self.model)


def show(client, label):
    print(f"\n-- {label}")
    try:
        response = client.chat(MSGS)
        print(f"   answer: {response.text!r}  (answered_by={client.answered_by})")
    except AllModelsFailed as exc:
        print(f"   AllModelsFailed: {len(exc.attempts)} attempts")
    except errors.LLMError as exc:
        print(f"   RAISED {type(exc).__name__}: {exc.message}")
    for a in client.last_attempts:
        status = "ok" if a.ok else ("skipped" if a.skipped else repr(a.error))
        print(f"     {a.model:<8} {status}")


def no_sleep(_seconds):
    pass


print("=" * 72)
print("1. THEIR PROBLEMS: fall through")
print("=" * 72)
primary = ScriptedClient("sonnet", lambda n: errors.RateLimitError("429 slow down",
                                                                     status_code=429))
backup = ScriptedClient("gpt-4o", lambda n: "summary from gpt-4o")
show(FallbackClient([("sonnet", primary), ("gpt-4o", backup)]), "primary rate-limited")

primary = ScriptedClient("sonnet", lambda n: errors.ServerError("503", status_code=503))
backup = ScriptedClient("gpt-4o", lambda n: errors.TimeoutError("read timed out"))
show(FallbackClient([("sonnet", primary), ("gpt-4o", backup)]), "everyone is down")

print("\n" + "=" * 72)
print("2. RETRY FIRST, THEN FALL BACK")
print("=" * 72)
primary = ScriptedClient("sonnet", lambda n: errors.RateLimitError("blip")
                         if n == 1 else "summary from sonnet")
backup = ScriptedClient("gpt-4o", lambda n: "summary from gpt-4o")
show(FallbackClient([("sonnet", primary), ("gpt-4o", backup)],
                    attempts_per_model=2, sleep=no_sleep),
     "one 429 blip, attempts_per_model=2")
print(f"   sonnet calls={primary.calls}, gpt-4o calls={backup.calls}")
print("""
   A single blip should not move you off your primary model: the backup may
   be a different vendor with a different prompt format, different tool-call
   quirks, and different prices. Retry absorbs the blip; fall back on the outage.
""")

print("=" * 72)
print("3. YOUR PROBLEMS: stop")
print("=" * 72)
typo = errors.BadRequestError("404 model 'anthropic/claude-sonet-4.5' not found",
                              status_code=404)
primary = ScriptedClient("sonnet", lambda n: typo)
backup = ScriptedClient("gpt-4o", lambda n: "summary from gpt-4o")
show(FallbackClient([("sonnet", primary), ("gpt-4o", backup)]), "a typo in the model id")
print(f"   gpt-4o calls={backup.calls}")


class NaiveFallback:
    """What people write first: catch EVERYTHING and move on."""

    def __init__(self, clients):
        self.clients = clients

    def chat(self, messages):
        for _, client in self.clients:
            try:
                return client.chat(messages)
            except Exception:  # noqa: BLE001 - this is the mistake being shown
                continue
        raise RuntimeError("all failed")


primary = ScriptedClient("sonnet", lambda n: typo)
backup = ScriptedClient("gpt-4o", lambda n: "summary from gpt-4o")
naive = NaiveFallback([("sonnet", primary), ("gpt-4o", backup)])
for _ in range(1000):
    naive.chat(MSGS)
print(f"""
   The naive version "works": 1000 requests, 1000 answers. It also sent
   {primary.calls} doomed requests to a model id that does not exist, and EVERY answer
   came from the backup. Your primary model has not served one request since
   the deploy with the typo, and nothing anywhere says so.""")

print("\n" + "=" * 72)
print("4. AN OUTAGE: with and without a breaker per model")
print("=" * 72)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


DOWN_UNTIL = 40.0      # the primary is down for the first 40 "seconds"

for use_breaker in (False, True):
    clock = Clock()
    # Time-based, not call-based: an outage lasts as long as it lasts, however
    # many requests you send at it. A call-based fake would never "recover"
    # for the breaker, which sends fewer calls (Chapter 13's example, again).
    primary = ScriptedClient("sonnet", lambda n: errors.ServerError("503")
                             if clock.now < DOWN_UNTIL else "summary from sonnet")
    backup = ScriptedClient("gpt-4o", lambda n: "summary from gpt-4o")
    breakers = ({"sonnet": CircuitBreaker(failure_threshold=3, reset_timeout_s=10,
                                          clock=clock)}
                if use_breaker else None)
    client = FallbackClient([("sonnet", primary), ("gpt-4o", backup)], breakers=breakers)
    for _ in range(100):
        client.chat(MSGS)
        clock.now += 1.0              # one request per "second"
    label = "with breaker" if use_breaker else "no breaker"
    print(f"  {label:<13} sonnet calls={primary.calls:>3}  "
          f"served_by={dict(client.served_by)}")
print("""
   Without a breaker every request during the outage pays for a failed call to
   the primary first: a full timeout in real life, before the backup even
   starts. With one, after 3 failures the primary is skipped outright and
   probed again every 10 seconds.

   Notice the breaker version moves traffic back to sonnet a little LATER than
   sonnet recovers (at 40s): it only notices on the next probe, and needs
   success_threshold good probes before it fully closes. That is the price of
   not hammering a recovering provider. And it is why `served_by` belongs on
   a dashboard: it tells you which model your users are actually getting.""")
