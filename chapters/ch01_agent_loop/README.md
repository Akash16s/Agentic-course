# Chapter 1 — The Agent Loop

---

## After this chapter you can

- Explain what an agent is in one sentence, and defend why a chatbot isn't one
- Describe exactly what happens on the wire when you "call an LLM"
- Explain why the model has no memory, and what that forces *you* to build
- Write a provider-agnostic LLM client with retries, timeouts and cost tracking
- Stream tokens as they arrive
- Read a token bill and predict what a feature will cost before you build it

---

## 1. The one idea

An agent is **a loop around a language model that can take actions**.

That's it. Everything else in this course — memory, planning, evals, multi-agent — is detail
hung off that sentence. Burn the loop into your head now:

```
                 ┌──────────────────────────────────────┐
                 │                                      │
                 ▼                                      │
        ┌─────────────────┐                             │
        │  1. THINK       │   send the whole            │
        │  call the LLM   │   conversation so far       │
        │  with context   │   to the model              │
        └────────┬────────┘                             │
                 │                                      │
                 ▼                                      │
        ┌─────────────────┐                             │
        │  2. DECIDE      │   did the model produce     │
        │  text or tool?  │   an answer, or ask to      │
        └───┬─────────┬───┘   use a tool?               │
            │         │                                 │
       text │         │ tool call                       │
            │         ▼                                 │
            │  ┌─────────────────┐                      │
            │  │  3. ACT         │  YOUR code runs      │
            │  │  run the tool   │  the function        │
            │  └────────┬────────┘                      │
            │           │                               │
            │           ▼                               │
            │  ┌─────────────────┐                      │
            │  │  4. OBSERVE     │  append the result   │
            │  │  append result  │  to the conversation ├──┘
            │  └─────────────────┘                      
            │
            ▼
        ┌─────────────────┐
        │     DONE        │  return the answer
        └─────────────────┘
```

Read it again. `THINK → DECIDE → ACT → OBSERVE → THINK → ...` until the model stops asking
for tools.

Three things people get wrong about this diagram, and it costs them weeks:

**The model never runs anything.** In step 3, *your* code runs the tool. The model emits some
JSON that says "I would like to call `get_weather` with `{"city": "Delhi"}`". It's a request,
not an execution. The model is a text generator that has been trained to emit
function-call-shaped text. Everything else is your program.

**The loop is your program's loop.** It is a `while` loop you write. There is no agent
running somewhere. If your process dies mid-loop, the agent is gone — which is why
Chapter 15 is about durable state.

**Nothing persists between iterations except what you resend.** More on this in §3, because
it's the single most important mechanical fact in this course.

## 2. Chatbot vs Workflow vs Agent

People use "agent" for everything, which makes the word useless. Here's the distinction that
actually matters — **who decides what happens next**:

| | Who picks the next step | Example | Use when |
|---|---|---|---|
| **Chatbot** | Nobody, there's one step | "Summarise this email" | One LLM call solves it |
| **Workflow** | *You* do, at build time | Extract → classify → route → draft. Fixed graph. | You know the steps in advance |
| **Agent** | *The model* does, at run time | "Find why the deploy failed and fix it" | The steps depend on what's found along the way |

The honest take that most tutorials won't tell you: **most production "AI features" should be
workflows, not agents.** Workflows are cheaper, faster, testable, and debuggable. You reach
for an agent when the path genuinely can't be known in advance.

A good rule: if you can draw the flowchart, build the flowchart. Agents are for when you
can't draw it.

We're learning agents because they're the harder case and they contain the workflow case. But
carry that scepticism — you'll need it when someone asks you to put an agent somewhere a
`for` loop belongs.

## 3. What an LLM API call actually is

Let's remove all the magic. Here is a complete LLM call, no SDK:

```http
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer sk-or-v1-...
Content-Type: application/json

{
  "model": "anthropic/claude-haiku-4.5",
  "messages": [
    {"role": "system",    "content": "You are terse."},
    {"role": "user",      "content": "Capital of France?"},
    {"role": "assistant", "content": "Paris."},
    {"role": "user",      "content": "And its population?"}
  ],
  "max_tokens": 200,
  "temperature": 0.7
}
```

And the response:

```json
{
  "id": "gen-abc123",
  "choices": [{
    "message": {"role": "assistant", "content": "About 2.1 million in the city proper."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 31, "completion_tokens": 12, "total_tokens": 43}
}
```

That's the whole thing. One HTTP POST. One JSON response. Every agent framework on earth is
built on top of this request.

### 3.1 The most important fact in this course: it is stateless

Look at the request again. You sent the **entire conversation**. Every time.

The model has no memory. None. It is a pure function:

```
response = f(messages, parameters)
```

Same messages in, (roughly) same answer out. Between two API calls the model retains
absolutely nothing about you. The illusion of a chatbot "remembering" your name is just your
client resending the message where you said it.

**Consequences you will feel all course:**

1. **You own the state.** Memory isn't a model feature, it's an application feature you build.
   That's why two whole chapters (5 and 6) are about memory.
2. **Every turn re-costs the whole history.** Turn 20 of a conversation sends turns 1–19
   again. Cost grows *quadratically* with conversation length if you don't manage it.
   A 50-turn agent run can cost 30× what you'd naively estimate.
3. **The context window is a hard wall.** When history + tools + system prompt exceed it, the
   call fails. You need trimming, summarisation, compaction (Chapters 4 and 5).
4. **Debugging is reproducible.** Log the exact `messages` array and you can replay any bug
   perfectly. Get in the habit now: *log the full request*.

> **Aside — "but prompt caching?"** Providers can cache the unchanged prefix of your messages
> so re-sending it is ~10× cheaper and faster. That's an optimisation on top of statelessness,
> not an exception to it. You still send everything. Chapter 13.

### 3.2 Roles

Four roles. That's the whole vocabulary.

- **`system`** — the standing instructions. Persona, rules, output format, available context.
  Sent first, applies to everything after. Models are trained to weight it heavily.
- **`user`** — input from the human (or from the outer program).
- **`assistant`** — what the model said previously. You replay these back to give it history.
  **This is also how you fake a memory** — you can *write* assistant messages the model never
  actually produced, and it will believe it said them. Useful and slightly disturbing.
- **`tool`** — the result of a tool your code ran. Chapter 2.

### 3.3 Tokens

Models don't see characters, they see **tokens** — chunks of roughly 4 English characters,
or ~0.75 words. `"unbelievable"` might be `["un", "bel", "iev", "able"]`.

Three reasons you must care:

- **You're billed per token**, input and output separately, at different rates. Output is
  typically 3–5× the price of input.
- **The context window is measured in tokens.** 200k context = 200k tokens of
  system + history + tools + the answer being generated.
- **Latency scales with tokens.** Specifically with *output* tokens — see §5.

Rough conversions to carry in your head:

| | Tokens |
|---|---|
| 1 English word | ~1.3 |
| 1 page of text | ~500 |
| This chapter's README | ~6,000 |
| A 300-line Python file | ~4,000 |
| An average codebase file tree | ~2,000 |

For a fast estimate: **`len(text) / 4`**. That's within ~15% for English prose and it's what
you'll implement in Exercise 1. Exact counts need the model's own tokenizer, which differs per
model family — and through OpenRouter you can't always know which one. So: estimate locally
for budgeting, trust `usage` in the response for billing.

### 3.4 Sampling parameters

The model outputs a **probability distribution over every possible next token**. Sampling
parameters control how you pick from that distribution.

- **`temperature`** (0–2, default ~1). Flattens or sharpens the distribution.
  `0` = always take the most likely token (deterministic-ish, repetitive).
  `1` = sample honestly from the distribution.
  `>1` = deliberately weird.
  **For agents, use 0 to 0.3.** You want reliable tool calls, not creativity. Creative writing
  is the only reason to go above 0.7.
- **`max_tokens`** — hard cap on the *output*. Not a suggestion to be brief; a guillotine. The
  model gets cut off mid-sentence and `finish_reason` comes back `"length"`. **Always set it.**
  It's your only defence against a model that decides to write an essay.
- **`top_p`** (nucleus sampling) — only sample from the smallest set of tokens whose
  probabilities sum to `p`. `0.9` cuts the long tail of nonsense. Tune temperature *or* top_p,
  not both; you'll just confuse yourself.
- **`stop`** — list of strings that halt generation when produced.
- **`seed`** — some providers accept it for reproducibility. Treat it as best-effort. LLM
  inference is not bit-reproducible in practice (batching and floating-point non-associativity
  on GPU).

**`finish_reason` is the field juniors ignore and seniors always check:**

| Value | Meaning | What you do |
|---|---|---|
| `stop` | Model finished naturally | Normal path |
| `length` | Hit `max_tokens` | Output is **truncated**. Any JSON in it is now invalid. Handle it. |
| `tool_calls` | Model wants a tool | Run it, loop (Chapter 2–3) |
| `content_filter` | Blocked by safety | Surface it, don't retry blindly |

If you never check `finish_reason`, you *will* one day spend an afternoon debugging a JSON
parse error that was really a truncation.

## 4. Why we wrap the provider

You'll write `agentlib/llm.py` — a thin layer over the API. Not because abstraction is
virtuous, but for four concrete reasons:

1. **Swap models in one place.** You'll switch models constantly: cheap one for dev, strong
   one for evals, another when one is down.
2. **Cross-cutting concerns live in one place.** Retries, timeouts, logging, cost tracking,
   tracing. Chapters 12 and 13 bolt onto this one file.
3. **Testability.** If every call goes through one class, you can inject a fake and your
   entire test suite runs offline for free. This is why the tests in this course cost $0.
4. **Providers differ in ways that leak.** Anthropic wants the system prompt as a top-level
   param; OpenAI wants it as a message. Tool-call formats differ. OpenRouter papers over most
   of it, but not all.

Keep it **thin**. A wrapper that hides `usage` or swallows errors is worse than no wrapper.

## 5. Cost and latency — the numbers to carry

Prices move; the *shape* doesn't. As of writing, per **million tokens**:

| Tier | Input | Output | Examples |
|---|---|---|---|
| Small | $0.10–1.00 | $0.40–5.00 | Haiku, gpt-4o-mini, Gemini Flash |
| Frontier | $3.00–15.00 | $15.00–75.00 | Sonnet, Opus, GPT-4o/5 |

**Worked example — the quadratic trap.** A 20-turn agent conversation. Each turn adds ~500
tokens of user + assistant text. Turn *n* sends ~500n input tokens.

Total input over 20 turns = 500 × (1+2+...+20) = 500 × 210 = **105,000 tokens** — not the
10,000 you'd guess from "20 turns × 500 tokens". Ten times more.

At $3/M input that's $0.32 per conversation. Ten thousand conversations a day = **$3,150/day**.
That number is why Chapters 4, 5 and 13 exist.

**Latency** splits into two phases:

- **Prefill / TTFT** — processing your input. Fast and parallel; roughly flat in input size
  until you get to very long contexts. Typically 200ms–2s.
- **Decode / TPOT** — generating output, strictly **one token at a time**, sequentially.
  ~10–50ms per token.

So: **output length dominates latency, input length dominates cost.** A 1,000-token answer
takes ~20 seconds no matter how fast your network is. This is also why streaming matters so
much — it doesn't make anything faster, it just means the user sees the first token in 500ms
instead of staring at a spinner for 20s.

## 6. What you're building in this chapter

Five components, each an exercise, each tested:

1. **`estimate_tokens`** — a local, free token estimator for budgeting
2. **`Conversation`** — the state object that makes the stateless model feel stateful
3. **`chat_with_retry`** — resilience: backoff, jitter, which errors to retry
4. **`CostTracker`** — every call accounted for, in dollars
5. **`stream_chat`** — tokens as they arrive

Then you assemble them into a working CLI chat that shows live cost. That is the skeleton
every remaining chapter builds on.

## 7. Common mistakes (I've made all of these)

1. **Forgetting to append the assistant's reply to history.** The model then repeats itself
   forever and you think it's broken. It isn't; you dropped its turn.
2. **Not setting `max_tokens`.** One runaway generation, one surprising bill.
3. **Not checking `finish_reason`.** Silent truncation, mysterious downstream failures.
4. **Retrying a 400.** Retries are for 429 and 5xx. A 400 means *your request is malformed* —
   retrying it just fails slower and, on some endpoints, still costs you.
5. **Retrying with no jitter.** All your workers back off in lockstep and hammer the API in
   synchronised waves. Always randomise the delay.
6. **Mutating the message list in place** while iterating over it. Copy, or use a real state
   object. This is Exercise 2's whole point.
7. **Trusting `len(text)/4` for billing.** It's for *budgeting*. Bill from `usage`.
8. **Using temperature 1.0 for agents.** Then wondering why tool arguments are inconsistent.

## 8. Exercises

In `exercises/`. Read each file's docstring — it specifies the contract precisely.

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_tokens.py` | `estimate_tokens`, `estimate_messages_tokens` |
| 2 | `exercise_2_conversation.py` | `Conversation` — add/copy/render/trim |
| 3 | `exercise_3_retry.py` | `chat_with_retry` — classify errors, exponential backoff + jitter |
| 4 | `exercise_4_cost.py` | `CostTracker` — per-call and cumulative spend |
| 5 | `exercise_5_stream.py` | `stream_chat` — yield deltas, accumulate the full text |
| 6 | `exercise_6_repl.py` | **Integration:** a real CLI chat using all of the above (needs your key) |

Run them:

```bash
pytest chapters/ch01_agent_loop/tests -q            # all
pytest chapters/ch01_agent_loop/tests -q -k tokens  # just exercise 1
pytest chapters/ch01_agent_loop/tests -q -x         # stop at first failure
```

Exercises 1–5 are tested **offline** against a fake client. No key needed, no cost. Exercise 6
is the one you run by hand against OpenRouter.

**Do them in order.** Each one is used by the next.

## 9. Check yourself

Answer from memory, out loud, before looking anything up. If you can't answer #3 and #7
cleanly, re-read §3.1 and §5 — the rest of the course leans on them.

1. What are the four steps of the agent loop, and who executes step 3?
2. Your user says "my name is Akash" in turn 1 and "what's my name?" in turn 8. Mechanically,
   how does the model know?
3. Why does a 40-turn conversation cost far more than 2× a 20-turn one?
4. `finish_reason` comes back as `"length"`. What just happened, and what's now unsafe to do
   with the response body?
5. You get an HTTP 400 and an HTTP 429. Which do you retry, and why not the other?
6. Why add random jitter to backoff delays?
7. A user complains your agent "feels slow". Its answers are ~800 tokens. Where is the time
   actually going, and does a faster network fix it?
8. When should you build a workflow instead of an agent?
9. Why is `temperature=0` usually right for an agent and wrong for a copywriting tool?
10. Why does every call in this course go through one wrapper class?

## 10. Going deeper (optional)

- Anthropic, *Building Effective Agents* — the workflow-vs-agent taxonomy, from the source
- OpenRouter docs → Models & Parameters — see the real price table and per-model quirks
- Karpathy, *Let's build the GPT Tokenizer* (YouTube) — 2 hrs, and tokens stop being magic

---

**When your tests are green, tell me.** I'll promote your work into `agentlib/` and open
Chapter 2, where the model stops just talking and starts calling functions.
