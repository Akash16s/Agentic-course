# Chapter 15 — Serving & Scale

**Prerequisite:** Chapters 1–14 green. Second-longest chapter; split it over two sessions.

---

## After this chapter you can

- Put an agent behind an HTTP API that serves many users at once
- Stream tokens to a browser over SSE, including when things fail mid-stream
- Choose correctly between sync, request-scoped async, and a job queue
- Make a run survive a deploy, an OOM kill and a rolling restart
- Explain why one blocking call in one tool can freeze every user's request

---

## 1. The one idea

**A long-running, expensive, stateful operation does not fit in an HTTP request.**

A typical agent run is 10 seconds to 5 minutes. HTTP requests are expected to finish
in under 30. Load balancers time out. Browsers give up. Deploys kill connections. And
an agent run that dies at step 8 has spent the money and produced nothing.

Three shapes, and picking the wrong one is the main architectural mistake here:

| Shape | Latency it suits | Cost |
|---|---|---|
| **Sync request/response** | < 5s | simplest; blocks a worker the whole time |
| **Streaming (SSE)** | 5–60s | user sees progress; still holds a connection |
| **Job queue + polling** | > 60s, or anything that must survive | most machinery; the only one that survives a restart |

**The decision rule:** if the work must survive a deploy, it needs a queue. If the
user must see progress, it needs streaming. Most real systems need both — submit to a
queue, stream the progress.

## 2. Streaming with SSE

Server-Sent Events: a long-lived HTTP response, one-way, text frames. Simpler than
WebSockets and enough for an agent, which only pushes.

```
event: delta
data: {"text": "Hello"}

data: [DONE]
```

The format is small and unforgiving:

- `field: value` lines, then **a blank line to end the frame**. Forget the blank line
  and the client hangs forever with your bytes in a buffer. This is the classic SSE bug.
- **Multi-line data needs `data: ` on every line.** A JSON blob with newlines in it
  silently truncates otherwise.
- **Send an explicit `[DONE]`.** Browsers auto-reconnect on a bare stream close, so
  without a sentinel the client reconnects and you re-run the whole thing.

### Failing mid-stream

You cannot change the HTTP status after the first byte has gone. A failure at second
30 of a 60-second stream cannot become a 500.

So errors go **in** the stream:

```
event: error
data: {"error": "provider timeout"}
```

Clients must handle that event. If they don't, a mid-stream failure is indistinguishable
from a short answer — which is exactly the bug where users report "it just stopped".

## 3. Async, and the one rule

An agent spends nearly all its wall-clock waiting on someone else's network. Threads
handle that badly at scale: a thread is megabytes of stack, and a few hundred is your
ceiling. One event loop handles thousands of *waiting* requests on one core.

> **Never call a blocking function inside a coroutine.**

One `requests.get()`, one `time.sleep()`, one heavy `json.loads` in a tool freezes the
**entire loop** — every other user's request stops until it returns. This is the single
most common way an async service becomes mysteriously slow under load, and it is
invisible in development with one user.

```python
result = await asyncio.to_thread(blocking_tool, argument)
```

Everything blocking you cannot rewrite goes through `to_thread`.

### Bound your concurrency

```python
await gather_bounded(coros, limit=8)
```

Plain `asyncio.gather` over 500 coroutines opens 500 connections at once and
rate-limits you into a wall. A semaphore is four lines.

### Context vars, not thread-locals

Chapter 12's tracer used `threading.local()`. Under asyncio many tasks share one
thread, so thread-locals leak between users — one request's spans attach to another's
trace. The async equivalent is `contextvars.ContextVar`, which is what real OTel uses.

## 4. The job queue

```
POST /runs        -> 202 {"run_id": "abc"}     returns immediately
GET  /runs/abc    -> {"status": "running", ...}
GET  /runs/abc/stream -> SSE progress
```

Three properties that matter:

**Bounded.** An unbounded queue turns a traffic spike into unbounded memory and a
latency curve that goes vertical — users wait ten minutes for something that should
have been refused in ten milliseconds. Reject when full. Back-pressure is kinder than
false hope.

**Workers survive bad jobs.** One exception must fail the run, never the worker.

**Sentinel shutdown.** To stop, put one `None` per worker rather than flipping a flag.
A worker blocked in `get()` wakes immediately instead of after its poll timeout.

## 5. Durability

An agent run is minutes long and costs real money. If a worker dies mid-run:

- the work is lost
- the money is spent
- the row still says `RUNNING`, so the user waits for something that will never finish

**The fix is a row, not cleverness.** `RunStore` persists status, output, cost, steps
and `updated_at` at every transition. Then:

```python
store.reclaim_stale(older_than_s=300, max_attempts=3)
```

on worker startup and on a timer. Rows stuck in `RUNNING` with an old `updated_at` get
requeued.

**`max_attempts` is not optional.** A run that reliably crashes its worker will crash
every worker in turn — the poison-pill problem, and it takes down the fleet one pod at
a time. After N attempts, mark it `FAILED` and move on.

For truly long workflows, look at durable execution engines (Temporal, Restate,
DBOS) which checkpoint *between steps* rather than restarting the run. Chapter 7's
`Plan` is deliberately serialisable for the same reason.

## 6. Multi-user hygiene

- **`session_id` on everything.** Chapter 5's store keyed correctly; the HTTP layer
  has to pass it through.
- **Auth before anything else**, and check that *this* user owns *this* run before you
  return it. An agent that returns run `abc` to whoever asks is a data breach with
  extra steps.
- **Per-user rate limits and per-user budgets** (Chapter 13). A global budget means
  one user can exhaust everyone's.
- **A `trace_id` per request**, returned in the response headers, so a support ticket
  can be joined to a trace (Chapter 12).

## 7. Scaling out

- **Stateless workers.** All state in the store, so any worker can pick up any run.
  This is what the whole chapter is for.
- **Scale on queue depth**, not CPU. An agent process is ~0% CPU and 100% waiting;
  CPU-based autoscaling will never trigger.
- **Sticky sessions are a smell.** If a run only works on the worker that started it,
  you have state in the wrong place.
- **Graceful shutdown.** On SIGTERM: stop accepting, finish in-flight work, then exit.
  Kubernetes gives you ~30s; use it, or every deploy kills live runs.

## 8. Common mistakes

1. **Running an agent synchronously in a request handler.** Times out; blocks a worker.
2. **No blank line after an SSE frame.** Client hangs, and it looks like your bug.
3. **Multi-line data without a per-line `data: ` prefix.** Silent truncation.
4. **No `[DONE]` sentinel.** The browser reconnects and re-runs everything.
5. **Trying to return a 500 mid-stream.** Impossible; put it in the stream.
6. **A blocking call inside a coroutine.** Freezes every user, invisibly.
7. **Thread-locals under asyncio.** Traces cross between users.
8. **Unbounded `asyncio.gather`.** Instant self-inflicted rate limit.
9. **An unbounded queue.** Memory growth and vertical latency.
10. **A crashing job killing the worker.**
11. **No stale-run reclaim.** Rows stuck in RUNNING forever.
12. **No `max_attempts`.** One poison pill takes out the fleet.
13. **Not checking run ownership.** A data breach with extra steps.
14. **Autoscaling on CPU.** It never fires.
15. **No graceful shutdown.** Every deploy kills live runs.

## 9. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_sse.py` | `sse`, `sse_done`, `sse_error` — the framing |
| 2 | `exercise_2_runstore.py` | `Run`, `RunStore` — durable state and stale reclaim |
| 3 | `exercise_3_queue.py` | `JobQueue` — bounded, worker-safe, clean shutdown |
| 4 | `exercise_4_async.py` | `gather_bounded` and the blocking-call trap |
| 5 | `exercise_5_service.py` | **Integration:** a real FastAPI agent service |

```bash
pytest chapters/ch15_serving/tests -q
```

## 10. Check yourself

1. Three serving shapes. What is the rule for choosing?
2. What ends an SSE frame, and what happens if you omit it?
3. Why does multi-line data need a prefix per line?
4. Why send `[DONE]` rather than just closing?
5. Why can't a failure at second 30 be a 500? What do you do instead?
6. What does one `time.sleep()` in a tool do to an async service?
7. Why do thread-locals break under asyncio, and what replaces them?
8. Why bound a queue? What does an unbounded one actually cost a user?
9. Why a `None` sentinel per worker rather than a flag?
10. A worker is OOM-killed mid-run. Walk through what the user sees, and what fixes it.
11. What is the poison-pill problem and which parameter prevents it?
12. Why scale on queue depth rather than CPU?
13. What does a sticky session tell you about your architecture?

---

**Next:** Chapter 16 — MCP, the protocol for sharing tools between agents.
