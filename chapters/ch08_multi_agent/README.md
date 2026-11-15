# Chapter 8 — Multi-Agent Systems

**Prerequisite:** Chapters 1–7 green.

---

## After this chapter you can

- Argue the case *against* multi-agent, and recognise when it doesn't apply
- Build the three patterns that actually earn their keep: router, orchestrator-worker,
  blackboard
- Hand off between agents without the receiving agent starting from zero
- Explain why two agents cost more than twice one agent

---

## 1. Read this before you build anything

**Most multi-agent systems should be one agent.**

The pitch is seductive: a Researcher, a Writer and a Critic, each with a focused
prompt, collaborating. It demos beautifully. In production it usually turns out to be
one agent's job, distributed across three, with a coordination bug in the middle.

What you pay:

- **Cost is superlinear.** Each agent has its own system prompt, its own tool
  schemas, its own history. Three agents is not 3× one agent — the orchestrator also
  pays to read every worker's output, and the workers pay to be told their context.
- **Latency stacks** wherever agents are sequential.
- **Information is lost at every boundary.** Agent A knows something in its context
  that agent B needed and never receives. This is the dominant failure mode and it is
  nearly invisible: B produces a confident, uninformed answer.
- **Debugging gets much harder.** Which agent was wrong? Or was the handoff wrong?
- **Errors compound.** Four agents at 90% each is 66% end to end.

**Try these first, in order:**

1. A better system prompt.
2. Better tool descriptions.
3. A workflow — a fixed sequence of LLM calls (Chapter 2, §2). Cheaper, testable,
   debuggable.
4. Planning (Chapter 7) — one agent, more structure.

Reach for multi-agent when one of these is true, and you can say which:

- **Parallelism is the point.** Ten independent research subtasks; running them
  concurrently is a 10× wall-clock win a single agent cannot get.
- **Genuinely incompatible contexts.** One task needs 50k tokens of legal text,
  another needs 50k of code. Putting both in one window makes both worse.
- **Different tools with real blast radius.** The agent that can delete production
  data should not be the same agent that reads untrusted web pages (Chapter 14).
- **An independent check is required.** A verifier that never saw the reasoning.

"It feels more organised" is not on that list.

## 2. Pattern 1 — Router

The cheapest pattern, and the one most often sufficient.

```
                 ┌────────┐
   request ─────►│ ROUTER │──► billing agent    (prompt + tools for billing)
                 │ (small │──► technical agent  (prompt + tools for tech)
                 │  model)│──► general agent
                 └────────┘
```

One cheap call picks a specialist; nothing else is distributed. You get focused
prompts and small toolsets without any coordination problem, because there is no
coordination — one agent handles the whole request.

Two implementation notes that matter more than they look:

**`when_not` beats `when`.** Routers over-route to whichever handler sounds most
capable. "Do NOT use for technical bugs" moves accuracy more than another sentence
describing what billing does.

**Parse leniently.** You ask for one word; you get "I'd route this to billing" about a
third of the time. Match the name anywhere in the reply, case-insensitively, and fall
back to a default rather than raising.

## 3. Pattern 2 — Orchestrator / worker

```
                  ┌──────────────┐
      goal ──────►│ ORCHESTRATOR │  splits into independent subtasks
                  └──────┬───────┘
              ┌──────────┼──────────┐
              ▼          ▼          ▼        (run concurrently)
          worker 1   worker 2   worker 3
              └──────────┼──────────┘
                         ▼
                  ┌──────────────┐
                  │ SYNTHESISER  │  one coherent answer
                  └──────────────┘
```

This is the one with a real, measurable advantage: **wall-clock**. Six independent
research subtasks take as long as the slowest, not the sum.

Rules:

- **Subtasks must be genuinely independent.** If worker 2 needs worker 1's output,
  you have a plan (Chapter 7), not a fan-out.
- **A failing worker returns a result with an error, never an exception.** Three of
  four succeeding is a usable answer with a caveat.
- **The synthesiser must SEE the failures.** Give it `[FAILED: ...]` explicitly. A
  synthesiser that cannot tell a worker failed will write a confident paragraph about
  the thing nobody researched. This is the single most common bug in this pattern.
- **Cap concurrency.** Twenty parallel workers is twenty rate-limit errors.

## 4. Pattern 3 — Blackboard

Agents don't message each other; they read and write shared state.

```
   agent A ──write──►┌─────────────┐◄──read── agent C
                     │ BLACKBOARD  │
   agent B ──read───►│ key → value │◄──write─ agent D
                     │ + audit log │
                     └─────────────┘
```

Why this over direct messaging: **decoupling**. An agent doesn't need to know who
produced a fact or who will consume it. Adding an agent doesn't change the others.

**Keep an append-only log of every write.** Without it you have several agents and no
idea who did what — and the characteristic blackboard bug is two agents overwriting
the same key, which is invisible in the final state and obvious in the log.

## 5. Handoffs

Transferring control. The field everyone forgets is `context`:

```python
Handoff(
    target="billing",
    reason="user is asking about an invoice",
    context="User is Akash, account 4471, disputing invoice INV-2201 for $340. "
            "Already confirmed the charge date is 2026-08-14.",
)
```

Without `context`, the billing agent starts from nothing and asks the user to repeat
what they already said. Every user has experienced this with a human support
transfer, and it is exactly as annoying when a machine does it.

**Summarise, don't forward the whole transcript.** Full history costs tokens and
carries the first agent's dead ends into the second agent's context.

## 6. Why it costs more than you think

A concrete sketch. One agent, 10 steps, 3k-token context average:

```
1 agent   : ~30k tokens
```

Three agents doing the same work:

```
orchestrator : planning + reading 3 worker outputs   ~15k
worker 1     : own system prompt + tools + context   ~12k
worker 2     : same                                  ~12k
worker 3     : same                                  ~12k
synthesiser  : all three outputs + instruction       ~10k
                                                     ~61k   ≈ 2x
```

Twice the tokens for work one agent could do. You bought wall-clock and prompt focus.
Sometimes that is exactly the right trade. It is never free, and "it feels cleaner" is
not a benefit you can put in a budget.

## 7. Common mistakes

1. **Multi-agent because it sounds better.** Say which of the four reasons applies.
2. **The synthesiser can't see failures.** Confident answers about nothing.
3. **Handoffs with no context.** The user repeats themselves.
4. **Forwarding whole transcripts on handoff.** Expensive, and carries dead ends.
5. **Sequential agents that could have been parallel.** You paid the cost, skipped
   the benefit.
6. **Unbounded fan-out.** Twenty workers, twenty 429s.
7. **A worker exception killing the run.** Partial results have value.
8. **No blackboard log.** Undebuggable.
9. **Two agents writing the same key.** Silent, and only visible in the log.
10. **Ignoring compounding error rates.** 0.9⁴ = 0.66.

## 8. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_blackboard.py` | `Blackboard` — thread-safe state with an audit log |
| 2 | `exercise_2_router.py` | `Route`, `Router` — lenient parsing, `when_not` |
| 3 | `exercise_3_orchestrator.py` | `Orchestrator`, `WorkerResult`, `fan_out` |
| 4 | `exercise_4_synthesis.py` | `Handoff`, `synthesis_prompt` |
| 5 | `exercise_5_research_team.py` | **Integration:** a real research team, measured against one agent |

```bash
pytest chapters/ch08_multi_agent/tests -q
```

## 9. Check yourself

1. Four legitimate reasons to go multi-agent. Which is the most common?
2. Three things to try first.
3. Why is three agents more than 3× the cost of one?
4. What is lost at every agent boundary, and why is it hard to notice?
5. Why does `when_not` improve routing more than a longer `when`?
6. Why parse the router's answer leniently?
7. What must the synthesiser be told about failed workers, and what happens otherwise?
8. What does a blackboard decouple?
9. What does the audit log let you catch that the final state cannot show?
10. Four agents at 90% accuracy each. End-to-end?
11. Which field of a handoff is most often missing, and what does the user experience?

---

**Next:** Chapter 8b (bonus) — the harness patterns behind modern coding agents: todo
lists, skills, subagents, the filesystem as memory. Or skip ahead to Chapter 9 — making output structured and reliable enough to build on.
