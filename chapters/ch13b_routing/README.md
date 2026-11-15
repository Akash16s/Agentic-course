# Chapter 13b — Model Routing, Fallbacks & Cascades

**Prerequisite:** Chapters 1–13 green. This one leans on Chapter 13's circuit breaker
and Chapters 10–11's evals.

---

## After this chapter you can

- Say why one model for everything is wasteful, with numbers
- Keep serving when a model is down, without hiding your own bugs
- Pick the cheapest model that can actually handle a request
- Route easy requests to a cheap model and hard ones to a strong one
- Run a cascade (cheap first, check the answer, escalate) and work out whether it saves money
- Measure a routing strategy on cost *and* quality, and notice when a provider changes a model under you

---

## 1. The one idea

**Different requests deserve different models. Some requests deserve a second model
when the first one falls over.**

Chapter 13 made one provider survivable. This chapter is about having more than one
model, and it covers two separate problems:

- **Availability.** The model is down, or slow, or rate-limiting you. Try another
  one. This is a *fallback*.
- **Cost.** The model is up, but it is the wrong price for this request. Pick a
  better one up front (*routing*), or try cheap first and check the answer
  (*cascade*).

Both are wrappers with the same `chat(messages)` interface as `LLMClient`. Your agent
loop from Chapter 3 does not know or care which one it is talking to. You've seen this
pattern before: Chapter 12's tracer and Chapter 13's cache work the same way.

## 2. One model for everything is a donation

Here is the same request, 1,500 tokens in and 400 out, priced from
`agentlib/pricing.py`:

| Model | $/call | vs cheapest |
|---|---|---|
| `openai/gpt-5-nano` | $0.00024 | 1× |
| `openai/gpt-5-mini` | $0.00118 | 5× |
| `anthropic/claude-haiku-4.5` | $0.00350 | 15× |
| `anthropic/claude-sonnet-4.5` | $0.01050 | 45× |
| `anthropic/claude-opus-4.1` | $0.05250 | 223× |

A **10–50× spread** between a small model and a frontier one is normal. Prices move all
the time, but the gap between the two ends has stayed about that wide.

Now look at what your traffic actually is. In most products, the bulk of requests are
easy: classify this, extract that, rephrase, answer a short factual question. A small
model gets those right. Sending them to a frontier model buys nothing except a bigger
invoice.

> If 70% of your traffic is easy and you send all of it to Sonnet, roughly two-thirds
> of your model bill buys nothing.

`examples/01_cascade_maths.py` prints these tables from the pricing file. Edit a price
and run it again.

## 3. Fallback chains

```python
client = FallbackClient([
    ("sonnet", LLMClient("anthropic/claude-sonnet-4.5")),
    ("gpt-4o", LLMClient("openai/gpt-4o")),
    ("llama",  LLMClient("meta-llama/llama-3.3-70b-instruct")),
])
response = client.chat(messages)
client.answered_by          # "gpt-4o" — Sonnet was rate-limited
```

### Fall back on their problems. Stop on yours.

This is the rule the whole chapter hangs on. Chapter 1's error hierarchy already
encodes it, in the `retryable` flag:

| Error | Whose problem | Fall back? |
|---|---|---|
| `RateLimitError` (429) | theirs: busy | **yes** |
| `ServerError` (5xx) | theirs: broken | **yes** |
| `TimeoutError`, `ConnectionError` | theirs, or the network | **yes** |
| `BadRequestError` (400/404/422) | **yours**: bad schema, bad model id, too long | **no** |
| `AuthError` (401/403) | **yours**: bad key, no credit | **no** |

Why never fall back on a 400? A malformed request is malformed everywhere, so falling
back just makes N slow failures where you had one fast one. The worse case is when the
fallback *does* work. Say your primary model id has a typo. Every request 404s, falls
through to the backup, and succeeds. Your users are happy, and nobody notices that
your primary model hasn't served one request since the deploy.
`examples/02_fallback_in_action.py` does exactly this, 1,000 times.

`except Exception: continue` is the most common fallback in the wild, and it is the
broken one.

### Retry first, then fall back

A single 429 blip should not move you to a different vendor. The backup model has a
different prompt style, different tool-calling quirks, and a different price. So
retry the same model a couple of times (Chapter 1's `chat_with_retry`), and fall back
only once that is exhausted.

```
for each model:
    retry with backoff (attempts_per_model)
    still failing with a retryable error?  -> next model
    non-retryable?                          -> raise, now
all failed -> AllModelsFailed(every attempt's error)
```

Don't put another retry *around* the whole chain. A 3-model chain with 3 attempts each,
wrapped in 3 outer retries, sends up to 27 requests for one user message, and it does
that at the exact moment every provider is struggling. That's why `AllModelsFailed` is
not retryable.

### Circuit breakers: skip a model you know is down

Without a breaker, every request during an outage first pays for a failed call to the
primary model, which in real life means a full timeout, and only then tries the
backup. Give each model its own Chapter 13 `CircuitBreaker`. When it is open, skip the
model **without calling it**.

Two details:

- **Only retryable errors count against the breaker.** A 400 means your request is
  broken and the provider is fine. If 400s tripped the breaker, one bad prompt would
  take a healthy model out of rotation.
- **Watch `served_by`.** If your primary model answers 99% of traffic on Monday and 60%
  on Tuesday, something happened on Tuesday. No alert fired, because every request
  still succeeded. The fallback hid the outage from your users, which is good, and
  from you, which is not.

### OpenRouter already does some of this

OpenRouter has two levels of fallback built in:

- **Across providers, for one model.** Many models are hosted by several providers.
  By default OpenRouter load-balances between them and moves to another provider when
  one errors. You can steer this with a `provider` object (`order`,
  `allow_fallbacks`, `sort` by price or throughput).
- **Across models.** Pass a `models` list and OpenRouter tries them in order:

```python
client.chat(messages, extra_body={
    "models": ["anthropic/claude-sonnet-4.5", "openai/gpt-4o"],
})
response.model     # the model that ACTUALLY answered — price this one, not the one you asked for
```

(`LLMClient.chat` passes extra keyword arguments straight to the SDK, so `extra_body`
just works.)

Use it. It's free, and it handles provider blips you would never see. You still want
your own chain as well, because:

- **Observability.** You see every attempt, every error and every `served_by` count.
  The built-in fallback gives you only the final `response.model`.
- **Per-model control.** Different models want different prompts, `max_tokens` or tool
  formats. Your chain can hold a differently configured client for each model.
- **Your breakers, your policy.** You decide what counts as down and for how long.
- **OpenRouter is a provider too.** If it is down, its fallback is down with it. Your
  chain can end at a direct vendor API or a self-hosted model.

If you use OpenRouter's fallback, **cost-track `response.model`**. Chapter 1's
`CostTracker` already does this. If you price the model you *asked* for, your numbers
will be wrong exactly on the days something went wrong.

## 4. Static routing: which models *can* serve this?

Before you ask which model *should* handle a request, rule out the ones that *can't*:

```python
spec = select_model(
    SPECS,
    input_tokens=40_000,
    output_tokens=2_000,       # room for the answer
    needs_tools=True,
    needs_vision=False,
)
```

The rules are boring, and that is a good thing:

- **Capability.** Needs tools? Images? JSON mode? Filter on it. A model without tool
  support will happily answer in prose, and your agent loop will treat that as "done".
- **Context fit, including the output.** 127k tokens of input in a 128k window
  "fits". Then the model has 1k tokens left to answer in and stops mid-sentence with
  `finish_reason == "length"`. Always check `input + output <= window`.
- **Task type.** Some kinds of work set a minimum tier: code review goes to tier 2 or
  above, whatever its length. That's a lookup table (`TASK_MIN_TIER`), not a model call.
- **Then the cheapest.** "Cheapest" depends on the request. A model with cheap input
  and expensive output wins long-document summaries and loses long-form writing. So
  price each request, instead of sorting the list once at startup.

When nothing fits, **say why, per model**:

```
NoModelFits: frontier: tier 3 above max_tier 2; mid: context 200,000 < 600,000 in + 1,024 out; nano: no vision support
```

`NoModelFits` is a `BadRequestError`, so a `FallbackClient` will correctly refuse to
fall back on it. A request that is too long for every model stays too long however
many times you retry.

Static rules are free and deterministic, and they're easy to explain to the next
engineer. Start with them, and add the cleverer routing below only once you have
measured that you need it.

## 5. Dynamic routing: which model *should* serve this?

The idea is to predict how hard a request is, then pick a tier from that. A different
problem from Chapter 8's `Router`, which picks a *specialist* (a prompt and toolset).
You can use both: Chapter 8 picks the specialist, this picks the model it runs on.

### A heuristic router: free and instant

Score surface features of the request:

| Feature | Why it hints at difficulty |
|---|---|
| Length | Long inputs need more synthesis |
| Code blocks | Code questions punish weak models |
| Keywords: "prove", "step by step", "refactor", "debug" | The user is telling you |
| Several questions | Several things to get right |

Add up the score and compare it with a threshold to choose a tier. It costs nothing,
adds no latency, and is wrong regularly. "What's 2+2? And 3+3? And 4+4?" scores as
hard. "Why does my distributed lock occasionally allow two holders" scores as easy.
That's fine **as long as you measure how often it is wrong** (§7).

Cap each feature's contribution. Otherwise one prompt that says "debug" five times
outscores everything else.

### An LLM router: a small model classifies

```python
router = LLMRouter(LLMClient("openai/gpt-5-nano"))
router.route("Prove that the square root of 2 is irrational")   # -> hard
```

This is better at meaning than the heuristic. Three things to get right:

- **Define the labels in the prompt.** Ask "is this hard?" with no definition and you
  get vibes.
- **Parse defensively.** You will get "Hard.", "**easy**" and "This task is hard". You
  will also get "hardly anything to it", where a substring match on "hard" sends a
  trivial request to the expensive model. Match whole words. If both labels appear,
  or neither, the answer is *unknown*.
- **Default to the strong tier.** See the asymmetry below.

**The router costs something too.** Classifying with a nano model is about 300 tokens
in and 1 out, roughly $0.00002. Next to a $0.0105 Sonnet call that's almost nothing.
The real cost is a **round trip of latency on every request**, often 200–500ms. Send
it only the first couple of thousand characters, and keep the heuristic router in
mind for latency-sensitive paths.

### Mis-routes are not symmetric

| Mistake | What it costs |
|---|---|
| Easy request -> strong model | About a cent. Nobody notices. |
| Hard request -> cheap model | A wrong answer in front of a user. A retry, a ticket, lost trust. |

So when the router is unsure, unparseable or down, **route to strong**. Tune the
threshold so that "hard sent to cheap" is rare, and accept more "easy sent to strong"
than feels efficient. A router that saves 60% and gets 5% of hard requests wrong is
usually worse than one that saves 40% and gets 1% wrong.

## 6. Cascades: try cheap, check, escalate

A router guesses *before* seeing an answer. A cascade looks at the answer:

```
cheap model -> answer -> check(answer)?  yes -> done
                                         no  -> strong model -> answer -> done
```

```python
cascade = Cascade(
    [("nano", LLMClient("openai/gpt-5-nano")),
     ("sonnet", LLMClient("anthropic/claude-sonnet-4.5"))],
    accept=lambda text: validate(extract_json(text), SCHEMA) == [],
)
result = cascade.run(messages)
result.model, result.accepted, result.total_cost
```

### The check is the whole thing

A cascade is only as good as `accept`. Use signals you can **check**:

| Signal | Good for |
|---|---|
| Schema validity (Chapter 9's `validate`) | Extraction, structured output |
| Tests pass | Code generation |
| Answer is in an allowed set | Classification |
| Well-formed tool call | Agent steps |
| A judge (Chapter 11) | Open-ended text. Costs a call, so add it to the cheap tier's cost |

**Don't trust self-reported confidence.** "Rate your confidence 1–10" measures how
sure the model sounds, and small models often sound most sure when they are wrong.
Checks have two ways to fail:

- **False accept.** A bad answer passes. The cascade looks cheap and quietly ships
  mistakes. This is the dangerous one.
- **False reject.** A good answer fails. You pay for both calls. Wasteful, but safe.

Measure your check on labelled data before you trust the cascade.

Two cheap rules your check should include anyway. A **truncated** answer
(`finish_reason == "length"`) is rejected automatically. And if your validator *crashes*
on garbage (say `json.loads` on prose), count that as a reject, not a crash.

### The maths

You **always** pay for the cheap call:

```
expected = p * c_cheap + (1 - p) * (c_cheap + c_strong)
         = c_cheap + (1 - p) * c_strong
```

where `p` is the fraction of cheap answers that pass. With nano at $0.00024, Sonnet at
$0.0105 and `p = 0.7`:

```
0.00024 + 0.3 * 0.0105 = $0.0034 per request     (68% cheaper than Sonnet alone)
```

The **break-even accept rate** is where the cascade costs the same as strong-only:

```
c_cheap + (1 - p) * c_strong = c_strong   ->   p = c_cheap / c_strong
```

For nano → Sonnet that's **2.2%**, almost nothing. For Haiku → Sonnet it's **33%**.
The cheap tier has to pass a third of the time just to break even.

### When cascades lose

- **Small price gap and low pass rate.** Haiku → Sonnet on traffic that is mostly hard
  costs *more* than Sonnet alone.
- **Latency budgets.** The *mean* goes down. But an escalated request takes cheap's
  time plus strong's time, which is slower than strong alone, and the escalated
  requests are the hard ones. With a p95 SLA, check the escalated path against it.
- **Streaming.** You can't stream the cheap answer to the user while you're still
  deciding whether to throw it away. A cascade means buffering.
- **Weak checks.** A check that can't tell good from bad turns a cascade into "always
  use the cheap model", and the cost is quality you don't see.
- **Extra tiers.** Each tier is a call that is pure overhead when it fails. Two tiers
  is the right default. Add a third only when data says it pays (example 01, part 5).

The same formula works for latency: put in seconds instead of dollars.

## 7. Measuring a router

A routing strategy is a change like any other, so it goes through the eval harness
(Chapters 10–11). Run the same eval set through each strategy and report **both** axes:

```
strategy        pass    cost      $/correct   p50
strong-only     19/20   $0.0410   $0.0022     1.9s
cheap-only      13/20   $0.0019   $0.0001     0.7s
router          18/20   $0.0150   $0.0008     1.2s
cascade         19/20   $0.0120   $0.0006     1.6s
```

(Illustrative numbers. Exercise 5 has you produce real ones.)

**The cost–quality frontier.** Plot each strategy at (cost, pass rate). A strategy is
**dominated** if some other strategy is both cheaper and at least as good. Throw
dominated strategies away. Choosing between the ones left on the frontier is a
business decision, not an engineering one. In the table above, `router` is dominated
by `cascade`: it costs more and passes fewer.

Also measure **the router itself**. Tag each eval case `easy` or `hard` and count the
confusion matrix. "Hard sent to cheap" is the cell that costs you answers.

Mind your sample size (Chapter 11, §5). On 20 cases, 18/20 against 19/20 is noise.
Read the results case by case with `compare_runs`. A strategy can tie on pass rate and
still break different cases.

### Silent regressions

You didn't change anything, and the numbers moved. Providers update models behind the
same id, change quantisation, or route you to a different host. **Re-run the suite on
a schedule**, not just when you change code, and compare with a saved baseline. A
router tuned on last month's cheap model can be wrong about this month's.

## 8. Pinning, deprecations, and "model ids change"

Chapter 1 told you to run `00_check_setup.py` before trusting the default model. This
is why:

- **Ids disappear.** `agentlib/pricing.py` still lists `google/gemini-2.0-flash-001`,
  which was delisted from OpenRouter while this course was being written. A
  hard-coded id in a fallback chain fails as `BadRequestError`, which (correctly)
  does not fall back. So your primary model breaks on the day it's removed.
- **Aliases move.** Some ids are aliases that the vendor re-points at newer snapshots.
  OpenAI's `gpt-4o` has pointed at several dated versions. Where a dated id exists,
  pinning to it means the model only changes when *you* change it.
- **Prices change.** Your `ModelSpec` table goes stale too. Load it from OpenRouter's
  `/models` endpoint at startup, or check it against that endpoint in CI.

What to do about it:

1. Model ids live in **config**, not scattered through code.
2. Check at startup that every id in your routing tables is still listed. Fail loudly
   at deploy time, not quietly at 3am.
3. Pin where you can. Treat a model upgrade like a dependency upgrade: run the evals
   first.
4. End every fallback chain with a model from a **different vendor**. Vendors have
   outages, and so do whole model families.

## 9. Common mistakes

1. **One frontier model for everything.** Most of the bill buys nothing.
2. **`except Exception: continue` in a fallback chain.** It hides your 400s and auth
   errors behind a backup that works.
3. **Falling back on a single blip.** Retry first. The backup is a different model with
   different behaviour.
4. **Retrying around the whole chain.** Traffic multiplies during exactly the outage
   you are trying to survive.
5. **Counting 400s against a breaker.** One bad prompt takes a healthy model out of
   rotation.
6. **Not tracking which model answered.** The fallback hides outages from you as well
   as from users.
7. **Pricing the model you asked for**, not `response.model`.
8. **Context fit without output headroom.** The answer gets cut off.
9. **Substring parsing of router output.** "hardly" means hard.
10. **Defaulting an unsure router to cheap.** Mis-routes are asymmetric. Default to
    strong.
11. **Trusting self-reported confidence as the cascade check.**
12. **Cascading with a small price gap.** Haiku → Sonnet needs a 33% pass rate to break
    even.
13. **Judging a router on cost alone.** Every router looks great if you don't measure
    quality.
14. **Hard-coded model ids with no startup check.** The chain breaks on deprecation day.

## 10. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_fallback.py` | `FallbackClient`: retry-then-fall-back, breakers, attempt log |
| 2 | `exercise_2_rules.py` | `estimate_cost`, `fits_context`, `select_model`, `select_for_task` |
| 3 | `exercise_3_router.py` | `HeuristicRouter`, `parse_label`, `LLMRouter`, `RoutedClient` |
| 4 | `exercise_4_cascade.py` | `Cascade`, `expected_cost`, `break_even_accept_rate`, the N-tier version |
| 5 | `exercise_5_frontier.py` | **Integration:** four strategies, one eval set, real models, one table |

```bash
pytest chapters/ch13b_routing/tests -q
```

## 11. Check yourself

1. Why is "one model for everything" wasteful? Give a rough price ratio.
2. Which errors should a fallback chain fall through on, and which should it re-raise?
   Why?
3. Describe how falling back on a 404 can hide a bug for weeks.
4. Why retry the same model before falling back? Why not retry around the whole chain?
5. Why shouldn't a `BadRequestError` count against a model's circuit breaker?
6. OpenRouter has a `models` fallback list. Name two reasons to keep your own chain
   anyway.
7. Why must context-fit checks include the output tokens?
8. Why default an unsure router to the strong model?
9. Write the expected-cost formula for a two-tier cascade, and derive the break-even
   accept rate.
10. Name three situations where a cascade loses.
11. Why is self-reported confidence a poor cascade check? What would you use instead?
12. What does it mean for a strategy to be "dominated" on the cost–quality frontier?
13. Your eval numbers moved and you changed nothing. Name two possible causes, and
    what you would do about each.

---

**Next:** Chapter 14 — the failures that are someone else's fault on purpose.
