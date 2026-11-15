# Chapter 3 — The ReAct Loop

**Prerequisite:** Chapters 1–2 green.

---

## After this chapter you can

- Write the agent loop from memory
- Name five ways a loop must be able to stop, and why three of them are non-negotiable
- Run parallel tool calls without corrupting the message ordering
- Return a *trace*, not just a string, and explain why that decides whether you can ever
  evaluate or debug the thing
- Diagnose the four classic loop pathologies on sight

---

## 1. The one idea

You have all the parts. The loop is twelve lines:

```python
while True:
    response = client.chat(conversation.messages, tools=registry.specs())
    conversation.add_response(response)

    calls = parse_tool_calls(response)
    if not calls:
        return response.text            # the model answered: we're done

    results = execute_tool_calls(registry, calls)
    conversation.extend(results)
```

**That is an AI agent.** Everything else in this course — and in every framework — is
about the `while True` being a lie.

## 2. ReAct: where the name comes from

"ReAct" = **Rea**son + **Act**, from a 2022 paper. The insight was that a model does far
better when it alternates thinking and doing, using each observation to inform the next
thought, than when it plans everything up front.

The original ReAct did this by *prompting*: "Thought: ... Action: ... Observation: ...",
parsed out of plain text with regexes. It was fragile and everyone who built one has a
story about the parsing.

Native tool calling replaced the regexes. The loop structure survived unchanged, and the
name stuck. When someone says "a ReAct agent" in 2026 they mean the loop above.

## 3. Stopping: the part that actually matters

`while True` has no exit. A real loop has five, and you need at least the first three.

### DONE — the model answered

No tool calls in the response. This is the intended exit and the only happy one.

### MAX_STEPS — the step budget

**Non-negotiable.** Without it a stuck agent runs until your money or your patience
ends. Set it to roughly 2–3× the steps a competent run needs: 10 for simple tasks, 30–50
for research or coding agents.

Hitting it is a *signal*, not just a limit. An agent that regularly hits max_steps has a
prompt problem or a tool problem, and the fix is upstream, not a bigger number.

### BUDGET — the spend limit

**Non-negotiable.** Steps are a bad proxy for money: one step that reads a 100k-token
file costs more than twenty small ones. This is Chapter 1's `CostTracker` earning its
place.

### TIMEOUT — wall clock

Needed as soon as anything sits behind a request. A user will not wait 4 minutes, and a
step limit does not bound time when a tool can hang.

### STOP_TOOL — an explicit terminator

Give the agent a `submit_answer(answer: str)` tool that raises `StopSignal`. Then
"finished" is an action it takes, not a behaviour you hope for.

Worth it when you need structured final output, or when the model tends to trail off
with "Let me also check..." forever. The cost is one extra tool in every request.

### The pattern to internalise

```python
for step in range(max_steps):        # NOT while True
    ...
return AgentResult(stop_reason=StopReason.MAX_STEPS, ...)
```

A `for` over a bounded range cannot run forever even if you make a mistake inside it.

## 4. Return a trace, not a string

The most consequential design decision in this chapter:

```python
def run(self, task) -> str:          # DON'T
def run(self, task) -> AgentResult:  # DO
```

`AgentResult` carries: `output`, `stop_reason`, `steps[]`, the final `conversation`,
`usage`, `cost`, and `error`.

Why it matters, concretely:

- **Evals** (ch 10–11) score *trajectories* — which tools, in what order. You cannot get
  that from a string.
- **Tracing** (ch 12) needs per-step timing and token counts.
- **Debugging.** "It gave a wrong answer" is unactionable. "It called `search` four times
  with the same query, then gave up at max_steps" names the bug.
- **Cost attribution.** Which step was expensive?

Each `Step` holds the response, the tool calls, the tool results and a duration. That is
your trace, and it costs nothing to collect.

## 5. Parallel tool execution

When the model requests three independent tools, running them one at a time wastes
wall-clock for no reason:

```python
with ThreadPoolExecutor(max_workers=min(8, len(calls))) as pool:
    return list(pool.map(self._run_one, calls))
```

`pool.map` preserves input order, which is what you need — the `tool_call_id`s pair
results to requests, but keeping order also keeps traces readable.

Threads, not asyncio, because tools are mostly I/O-bound and blocking (`requests`, file
reads, DB drivers). Chapter 15 does the async version properly.

**Three cautions:**

- **Tools that write shared state are no longer safe.** Two parallel calls appending to
  the same list, or writing the same file, will race. Either make tools pure, or
  serialise the ones that aren't.
- **Cap the workers.** `min(8, len(calls))` — a model asking for 40 tools should not open
  40 sockets.
- **Order in, order out.** Reordering results confuses models more than you'd expect.

In the example script, four 150ms tools take 0.63s serial and 0.16s parallel.

## 6. Error recovery inside the loop

Three different failure layers, three different responses:

| Layer | Example | Response |
|---|---|---|
| **Tool failed** | File missing, API 500 | Feed the error back as a tool result. The model retries or routes around it. (Chapter 2.) |
| **LLM call failed** | 429, timeout | `chat_with_retry` from Chapter 1. Transparent to the loop. |
| **Retries exhausted** | Provider down | Stop with `StopReason.ERROR`. Return everything gathered so far. |

That third row is worth dwelling on. When a run dies at step 8 of 10, return the partial
`AgentResult` — the steps, the cost incurred, the last text. Throwing it all away
discards the trace that tells you what happened, and the money is spent either way.

## 7. The four loop pathologies

You will meet all of these.

**The repeater.** Calls the same tool with the same arguments over and over. Usually the
tool returns something unhelpful ("no results") and the model has no other move. *Fix:*
better tool results, or detect a repeated (name, args) pair and inject a nudge.

**The ping-pong.** Alternates two tools forever, A-B-A-B. Usually contradictory
instructions, or two tools whose descriptions overlap. *Fix:* disambiguate the
descriptions.

**The premature quitter.** Answers before doing the work, often with "I would need to
check X". *Fix:* the system prompt should say to use tools rather than describe using
them; sometimes a `submit_answer` tool fixes it outright.

**The rambler.** Never stops, keeps finding one more thing to verify. *Fix:* an explicit
terminator tool, and a system prompt with a completion criterion.

All four are visible in one glance at `result.tool_sequence`. That is what the trace is
for.

## 8. Common mistakes

1. **`while True`.** Use a bounded `for`.
2. **Returning a string.** You have thrown away everything you need to improve the agent.
3. **Forgetting `conversation.add_response(response)` before the tool results.** 400.
4. **Losing steps on error.** Return the partial result.
5. **Only a step limit, no cost limit.** One giant tool result blows the budget in one step.
6. **Parallel tools that mutate shared state.** Intermittent, unreproducible bugs.
7. **Trimming history mid-loop and cutting between an assistant tool_calls message and
   its tool results.** The provider rejects the orphan. Trim in *pairs* (Chapter 4).
8. **`max_steps=100` "to be safe".** That is not safety, that is a bigger bill.

## 9. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_result.py` | `Step`, `AgentResult`, `StopReason` and their properties |
| 2 | `exercise_2_stop.py` | `check_stop_conditions` — the exit logic, in isolation |
| 3 | `exercise_3_parallel.py` | `run_tools` — ordered, bounded, parallel execution |
| 4 | `exercise_4_agent.py` | `Agent.run` — the whole loop |
| 5 | `exercise_5_pathologies.py` | `detect_repetition` — catch a stuck agent mid-run |
| 6 | `exercise_6_real_agent.py` | **Integration:** a real research agent (needs your key) |

```bash
pytest chapters/ch03_react_loop/tests -q
```

## 10. Check yourself

1. Write the agent loop from memory. Twelve lines.
2. Five stop reasons. Which three would you refuse to ship without?
3. Why is a step limit not a substitute for a cost limit?
4. Why return `AgentResult` rather than `str`? Give three concrete consequences.
5. Why does `pool.map` suit parallel tool calls better than `as_completed`?
6. A tool raises. What happens? Now: retries are exhausted on the LLM call. What happens?
7. Name the four pathologies and the first thing you'd check for each.
8. Why must trimming history respect assistant/tool message pairs?
9. When is an explicit `submit_answer` tool worth its token cost?
10. Your agent hits `max_steps` on 30% of runs. Is raising `max_steps` the fix?

---

**Next:** Chapter 4 — the loop works, but every step makes the context bigger. Context
engineering is how you stop that killing you.
