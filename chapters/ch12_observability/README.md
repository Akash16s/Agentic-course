# Chapter 12 — Observability & Tracing

**Prerequisite:** Chapters 1–11 green.

---

## After this chapter you can

- Instrument an agent with nested spans in one line per operation
- Read a trace and locate where the time and the money went
- Use thread-local state to track parentage without plumbing it through every call
- Wrap a client and a tool registry without touching their code
- Say what to log, what never to log, and what to sample

---

## 1. The one idea

**An eval tells you a case failed. A trace tells you why.**

Chapter 10 gave you a number. When the number drops, you need to see inside a single
run: which tool was called with what, what came back, how long each step took, where
the tokens went. Without that you are reading a final answer and guessing at forty
steps you cannot see.

Agents are unusually hard to observe:

- **Non-deterministic.** The same input takes a different path each time.
- **Deeply nested.** run → step → llm call → tool → (another agent).
- **Slow and expensive**, so "just run it again with prints" is a real cost.
- **The interesting failure is usually in the middle**, not at the end.

## 2. Spans

Borrowed wholesale from OpenTelemetry, because the model is right and because it
means you can swap this for real OTel later without changing how you think.

A **span** is one timed operation with a name, a parent, attributes, events and a
status. Spans nest into a tree:

```
- agent.run [agent] 4,210ms          task="find why the deploy failed"
  - llm.chat [llm] 890ms             model=haiku, tokens=1,204, cost=$0.0012
  - tool.read_file [tool] 12ms       path="deploy.log", result_chars=8,402
  - llm.chat [llm] 1,150ms           tokens=9,830, cost=$0.0098   <- the expensive one
  - tool.search [tool] 2,100ms       query="ImagePullBackOff"     <- the slow one
  - llm.chat [llm] 58ms
```

You can see immediately: the second LLM call cost 8× the first (the tool result went
into the context), and the search tool owns half the wall-clock. Neither is visible in
the final answer.

### The parts

| Field | Why |
|---|---|
| `name` | `agent.run`, `llm.chat`, `tool.read_file` — dot-namespaced so you can group |
| `parent_id` | builds the tree |
| `kind` | `agent` / `llm` / `tool` / `eval` — lets you sum cost across all LLM spans |
| `attributes` | the facts: model, tokens, cost, path, finish_reason |
| `events` | points in time inside a span: a retry, a cache hit, a decision |
| `status`/`error` | did it fail |

## 3. The thread-local trick

The thing that makes instrumentation one line instead of a refactor:

```python
with tracer.span("agent.run") as s:        # no parent
    with tracer.span("llm.chat") as s2:    # automatically a child of agent.run
        ...
```

The tracer keeps a **stack of open spans in thread-local state**. Opening a span
reads the top of the stack as its parent; closing pops it. Nothing has to pass a
parent id around, so instrumenting an existing function is genuinely one line.

Thread-*local* matters because Chapter 3 runs tools in a thread pool. Without it, two
parallel tools would fight over "the current span" and your tree would be nonsense.

> **A caveat worth knowing:** thread-local breaks under `asyncio`, where many tasks
> share one thread. The async equivalent is `contextvars.ContextVar`, which is what
> real OTel uses. Chapter 15 comes back to this.

### Never swallow the exception

```python
except Exception as exc:
    span.status = "error"
    span.error = f"{type(exc).__name__}: {exc}"
    raise                    # <- this line
```

A tracer that eats exceptions is a tracer that causes outages. Record and re-raise.

## 4. Instrumenting without touching the code

Wrap, don't subclass:

```python
client = TracedClient(LLMClient(), tracer)
tools  = TracedRegistry(registry, tracer)
```

Each has `__getattr__` delegating to the inner object, so it is a drop-in. It also
works with `FakeLLMClient`, which is why everything in this chapter is testable
offline.

**Trace the tool layer too.** An untraced tool layer makes an agent look like it spent
8 seconds thinking when it spent 7.5 of them waiting on one HTTP call. That mistake
sends people off optimising prompts when the problem is a slow API.

## 5. What to record

**Always:**
`model`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `finish_reason`, `duration`,
`tool name`, `result size`, `error`, and a `trace_id` you can grep for.

**Usually:** the prompt and response, for debugging — but see below.

**Never:**
- **API keys.** Obvious, and it still happens via a logged request object.
- **Raw PII**, unless you have decided to and can defend it. Chapter 9's `RedactPII`
  belongs on this path.
- **Whole 50k-token contexts on every span.** Store a hash and a truncated preview;
  keep full payloads for sampled traces only.

### Cardinality, briefly

If you export to a metrics system, do not put the user id, the trace id or the full
prompt in a metric *label*. Each distinct value creates a time series, and
high-cardinality labels are the classic way to take down a monitoring stack. Labels
are for `model`, `kind`, `status`. Everything else goes in the span.

### Sampling

Full tracing on every production request is expensive to store. The usual policy:

- **100% of errors.** Always. Those are the ones you need.
- **100% in development and in evals.**
- **1–10% of successful production requests**, for latency and cost trends.

## 6. What to do with a trace

Four questions it answers immediately:

1. **Where did the time go?** `slowest(5)`. Usually one tool, occasionally one
   enormous prompt.
2. **Where did the money go?** `sum_attribute("cost_usd")` grouped by span name. It is
   almost always the call right after a big tool result.
3. **What did it actually do?** The tool sequence, with arguments. This is where you
   spot the repeater from Chapter 3.
4. **What broke?** `errors()` — and the parent chain tells you what was happening
   around it.

### JSONL, appended

One span per line, appended to a file. That format lets you `cat` a week of traces
together, `grep` for a trace id, and load them into anything from `jq` to DuckDB. Do
not invent a format.

## 7. The tools you would use in production

You have now built the core of all of them: **Langfuse** (open source, good agent
support), **Braintrust** (evals and tracing together), **LangSmith** (tied to
LangChain), **Phoenix/Arize** (OSS, strong on evals), or plain **OpenTelemetry** into
whatever you already run.

Pick one when you ship. Build this one first so you know what it is doing — and so
that when a vendor's UI doesn't show you the thing you need, you know it exists in the
data.

## 8. Common mistakes

1. **No tracing until something breaks.** You cannot retroactively trace yesterday.
2. **Print statements instead of spans.** No tree, no timings, no grep.
3. **A tracer that swallows exceptions.** Now it causes outages.
4. **Global mutable "current span" instead of thread-local.** Parallel tools corrupt
   the tree.
5. **Only tracing LLM calls.** The tool layer is where the latency usually is.
6. **Logging whole contexts on every span.** Your storage bill overtakes your API bill.
7. **Secrets or PII in spans.**
8. **High-cardinality metric labels.** A classic way to fall over your monitoring.
9. **Sampling errors out.** Sample successes; keep every failure.
10. **A custom trace format.** Use JSONL and spend the time elsewhere.
11. **No `trace_id` linking an eval failure to its trace.** The two systems have to
    join up or neither is much use.

## 9. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_span.py` | `Span` — duration, attributes, events, serialisation |
| 2 | `exercise_2_tracer.py` | `Tracer.span` — nesting, thread-local, error capture |
| 3 | `exercise_3_analysis.py` | `root_spans`, `children_of`, `sum_attribute`, `slowest`, `render` |
| 4 | `exercise_4_instrument.py` | `TracedClient`, `TracedRegistry` — wrapping without touching |
| 5 | `exercise_5_debug_a_run.py` | **Integration:** trace a real agent and find the bug |

```bash
pytest chapters/ch12_observability/tests -q
```

## 10. Check yourself

1. What does a trace give you that an eval report cannot?
2. Name the six parts of a span and what each is for.
3. How does a span know its parent without being told?
4. Why thread-local rather than a plain attribute? What breaks otherwise?
5. Why does thread-local fail under asyncio, and what replaces it?
6. Why must a tracer re-raise?
7. Why wrap rather than subclass to instrument a client?
8. What goes wrong if you only trace LLM calls?
9. Three things you should never put in a span.
10. What is cardinality and why does it matter for metric labels?
11. A sensible sampling policy, and the one thing you never sample out.
12. Why JSONL, appended?

---

**Next:** Chapter 13 — you can see the problems now. Time to make them stop happening.
