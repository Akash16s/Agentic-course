# Chapter 13 — Production Hardening

**Prerequisite:** Chapters 1–12 green.

---

## After this chapter you can

- Cache safely, and say exactly when caching is wrong
- Stop a provider outage from taking your service down with it
- Rate-limit yourself before the provider does it for you
- Guard spend before the money is gone, not after
- Make a retried operation safe to retry
- Use provider prompt caching without accidentally busting it every call

---

## 1. The one idea

**Your agent works. Now assume everything around it doesn't.**

The provider will rate-limit you, go down, get slow, and change its pricing. Your
users will double-click. Your retries will duplicate side effects. An agent loop will
try to spend $400 in four minutes.

None of what follows is clever. All of it is the difference between a demo and
something you can leave running.

## 2. Caching

### The key must cover everything

```python
key = sha256(json.dumps({"messages": ..., "params": {...}}, sort_keys=True))
```

**Everything that affects the answer.** Same messages, different `temperature`, is a
different request. Same messages, different `tools`, is a different request. A cache
keyed on messages alone will serve you the wrong answer — silently, and only
sometimes, which is the worst kind of bug to chase.

`sort_keys=True`, so dict ordering can't change the key.

### Never cache non-deterministic requests

```python
if kwargs.get("temperature", 0.0):
    return self.inner.chat(...)      # the caller asked for variation
```

At `temperature > 0` the caller wants variety. Serving a cached answer quietly takes
it away, and the bug presents as "the model has become repetitive".

### LRU plus TTL

- **LRU** bounds memory. Touch on read, evict the least recent.
- **TTL** bounds staleness. An agent that caches a weather lookup for a day is worse
  than one that doesn't cache.

### Where it actually pays

- **Eval suites** (Chapter 10) re-run identical requests constantly.
- **Retries** after a downstream failure re-send the same request.
- **Agents re-asking the same sub-question** — more common than you'd think.

Your production hit rate on *user* traffic will be low. That's fine; the eval savings
alone justify it.

## 3. Circuit breakers

Without one, a provider outage becomes your outage:

```
provider slows down → every request waits for its timeout → workers all block
→ queue backs up → you are down too
```

A breaker converts a slow cascading failure into a fast obvious one.

```
CLOSED  --(N consecutive failures)--> OPEN
OPEN    --(reset_timeout elapses)---> HALF_OPEN
HALF_OPEN --(M successes)-----------> CLOSED
HALF_OPEN --(any failure)-----------> OPEN     (full timeout again)
```

Three details that matter:

- **`HALF_OPEN` exists so you probe with one request, not a thundering herd.** When
  the timeout expires, everything must not slam the recovering service at once.
- **A failure in HALF_OPEN goes straight back to OPEN**, with the full timeout. Half a
  recovery is not a recovery.
- **Reset the failure count on success in CLOSED.** You want *consecutive* failures,
  not a lifetime tally — otherwise a healthy service trips the breaker after a month.

Breaker plus retry (Chapter 1) is the right combination: retry the blips, break on the
outage.

## 4. Rate limiting yourself

Getting 429s is not a strategy. Limit yourself first.

**Token bucket**, not a fixed window: `rate` permits per second, accumulating up to
`capacity`. That allows a burst and then settles — which is what providers actually
permit. A strict "N per second" serialises work the provider would have taken all at
once.

```python
limiter = RateLimiter(rate=5, capacity=10)   # 5/s sustained, burst of 10
limiter.acquire()                            # blocks if needed
```

Real providers limit **both** requests/min and tokens/min. Two buckets, and
`acquire(estimated_tokens)` on the second.

## 5. Budget guards, before and after

Chapter 1's `CostTracker` raises on the call that crosses the line — **the money is
already spent**. That is the right accounting, and it is not a limit.

A pre-flight guard refuses the call using an *estimate*:

```python
guard.check(messages)     # raises BEFORE the call
response = client.chat(messages)
guard.record(actual_cost) # true accounting after
```

**You want both.** The estimate can be wrong in either direction, so you cap
optimistically and account honestly.

Budgets worth having: per run, per user per day, and a global kill switch. The last
one is the one you'll be glad of at 3am.

## 6. Idempotency

A client times out, retries, and your agent issues the refund twice. The network
cannot tell you whether the first attempt succeeded — only a key you control can.

```python
store.run(f"refund:{request_id}", lambda: agent.run(task))
```

Same key, same result, executed once. Notes:

- **The key comes from the caller**, not from a hash of the request. Two legitimate
  identical requests are not the same operation.
- **Track in-flight keys**, or two concurrent retries both start work.
- In production this is Redis or a unique constraint in your database, not a dict.
  The interface is the same, which is why building the dict version is useful.

## 7. Provider prompt caching

Different from §2. The *provider* stores the unchanged **prefix** of your request, so
re-sending it is roughly 10× cheaper and noticeably faster.

The rule is simple and easy to break:

> **The prefix must be byte-identical between calls.**

So: system prompt and tool definitions first, then history, then the new message. And
then the mistake everyone makes once:

```python
system = f"You are a helpful assistant. Today is {datetime.now()}."
```

That busts the cache on **every single call**, forever, and nothing tells you. If you
need the date, round it to the day — or put it in the first user message, after the
cacheable prefix.

Through OpenRouter, support and syntax vary by underlying model. Treat it as
best-effort and **measure whether it helped** rather than assuming.

## 8. Concurrency

- **Bound everything.** A `ThreadPoolExecutor` with no `max_workers` is how you open
  200 sockets.
- **Semaphore per provider**, not per process, when you talk to several.
- **Back-pressure.** When your queue is full, reject fast. Accepting work you cannot
  do just moves the failure somewhere less visible.

## 9. Common mistakes

1. **Caching on messages alone.** Wrong answers, intermittently.
2. **Caching at temperature > 0.** The model "becomes repetitive".
3. **Cache with no TTL.** Stale answers forever.
4. **No circuit breaker.** Their outage becomes yours.
5. **No HALF_OPEN.** Everything slams the recovering service at once.
6. **A lifetime failure counter.** The breaker trips on a healthy service eventually.
7. **Relying on 429s to pace yourself.** Slower and ruder than limiting yourself.
8. **A fixed-window limiter.** You serialise bursts the provider would have accepted.
9. **Only post-hoc cost tracking.** You find out after the $400.
10. **No idempotency on side-effecting agents.** Double refunds.
11. **A timestamp in the system prompt.** Prompt caching silently never works.
12. **Unbounded thread pools.**

## 10. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_cache.py` | `cache_key`, `ResponseCache`, `CachedClient` |
| 2 | `exercise_2_breaker.py` | `CircuitBreaker` — the full state machine |
| 3 | `exercise_3_ratelimit.py` | `RateLimiter` — token bucket |
| 4 | `exercise_4_guards.py` | `BudgetGuard`, `IdempotencyStore`, `mark_cacheable_prefix` |
| 5 | `exercise_5_hardened.py` | **Integration:** a fully hardened client, chaos-tested |

```bash
pytest chapters/ch13_hardening/tests -q
```

## 11. Check yourself

1. What must the cache key cover, and what breaks if it covers less?
2. Why must you not cache at temperature > 0? How does that bug present?
3. Why LRU *and* TTL?
4. Describe the cascade a circuit breaker prevents.
5. Why does HALF_OPEN exist? What happens if a probe fails?
6. Why consecutive failures rather than a total?
7. Why a token bucket rather than a fixed window?
8. Chapter 1's CostTracker vs a pre-flight guard: what does each give you?
9. Why must the idempotency key come from the caller?
10. Why track in-flight keys?
11. What single line silently disables provider prompt caching forever?
12. What is back-pressure, and why is accepting work you can't do worse than refusing it?

---

**Next:** Chapter 13b (bonus) — routing, fallbacks and cascades: stop paying frontier
prices for easy requests. Or skip ahead to Chapter 14 — the failures that are someone else's fault on purpose.
