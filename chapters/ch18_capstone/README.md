# Chapter 18 — Capstone

**Prerequisite:** Chapters 1–17 green.

---

## What this is

One real agent, built properly, with everything from the previous seventeen
chapters actually wired in — not mentioned, wired in. At the end you have something
you could show someone, and a set of numbers you can defend.

The acceptance suite (`tests/test_acceptance.py`) checks the *structure*: that the
pieces exist and are connected. It cannot check that your agent is good. That is
what your own eval suite is for, and building it is the point.

```bash
pytest chapters/ch18_capstone/tests -q
```

---

## 1. Pick a project

Any of these works. Pick the one you would actually use.

### A — Codebase Q&A agent
Answers questions about a repository. Tools: `list_files`, `read_file`, `grep`,
`submit_answer`. Memory of what it has already read. Good if you want the
retrieval and context chapters to bite.

### B — Support triage agent
Reads a ticket, classifies it, looks up account and policy, drafts a reply, and
escalates when it should. Good if you want permissions, structured output and
human-in-the-loop to bite.

### C — Research agent
Takes a question, plans sub-questions, gathers from a document corpus, synthesises
with citations. Good if you want planning, multi-agent and evals to bite.

### D — Your own
Better than all three, if you have one. It must involve at least four tools, at
least one irreversible action, and a question that genuinely needs several steps.

---

## 2. Requirements

Every item maps to a chapter. The acceptance suite checks the ones marked "auto".

| # | Requirement | Chapter | Checked by suite |
|---|---|---|---|
| 1 | A provider shim with retries and cost tracking | 1 | auto |
| 2 | At least 4 tools, schemas derived from signatures | 2 | auto |
| 3 | An agent loop with **all** the stop conditions | 3 | auto |
| 4 | Tool output bounded; context budgeted | 4 | auto |
| 5 | Sessions that survive a restart | 5 | auto |
| 6 | Long-term memory across sessions | 6 | auto |
| 7 | Planning **or** reflection, with a measured justification | 7 | |
| 8 | Multi-agent **or** a written argument for why not | 8 | |
| 9 | One structured output path with validation + repair | 9 | auto |
| 10 | ≥ 30 eval cases, ≥ 5 negative, in JSONL | 10 | auto |
| 11 | An LLM judge with a calibrated rubric, + trajectory checks | 11 | auto |
| 12 | Tracing on every run, exported to JSONL | 12 | auto |
| 13 | Caching, a circuit breaker, a rate limiter, a budget guard | 13 | auto |
| 14 | Default-deny permissions; a sandbox; HITL on the irreversible action | 14 | auto |
| 15 | An HTTP service: submit, poll, stream, and it survives a restart | 15 | auto |
| 16 | At least one tool exposed over MCP **or** consumed from MCP | 16 | auto |
| 17 | A written framework decision with reasons | 17 | |

### The three unchecked ones are the hardest

7, 8 and 17 are judgement, and judgement is what the course was for. Each needs a
paragraph in `DECISIONS.md` with **numbers**, not vibes:

> "Reflection: rejected. Measured over 30 eval cases, a critic with no extra
> information changed 3 answers, improved 1, cost +140%. Kept for the
> JSON-extraction path only, where the critic has the schema."

"I didn't need it" is fine. "It felt cleaner" is not.

---

## 3. Deliverables

```
capstone/
├── README.md          what it does, how to run it, what it costs
├── DECISIONS.md       requirements 7, 8, 17 + anything else you chose against
├── RESULTS.md         your numbers: pass rate, cost, latency, and the trend
├── agent.py           the agent, tools, prompts
├── service.py         the HTTP service
├── mcp_server.py      your MCP surface
├── evals/
│   ├── dataset.jsonl  >= 30 cases, >= 5 negative
│   ├── checks.py      assertions + judge + trajectory
│   └── run.py         the runner, with a CI gate
└── traces/            JSONL output (gitignored)
```

`RESULTS.md` is the one people skip and the one that matters most. It should
contain, at minimum:

- baseline pass rate with a confidence interval
- the three changes you made and what each did to the number
- cost per run and p50/p95 latency
- **one thing that got worse**, and what you did about it

A results file with no regression in it means you did not look hard enough.

---

## 4. Suggested order

Do not build it in requirement order. Build it in this order:

**Day 1 — the spine.** Tools, loop, one end-to-end run that works. Ugly is fine.

**Day 2 — the evals.** 30 cases, the runner, a baseline number. **Before** you
improve anything. You cannot improve what you have not measured, and a baseline
recorded after your improvements is worthless.

**Day 3 — memory and context.** Sessions, long-term memory, bounded tool output.
Re-run the evals after each. Write the numbers down.

**Day 4 — the judge and trajectories.** Calibrate the rubric against your own
grading on five cases before you trust it.

**Day 5 — hardening and security.** Cache, breaker, limiter, budget, permissions,
sandbox, HITL. Re-run the evals: did any of it change the answers? It should not.
If it did, find out why.

**Day 6 — the service and MCP.** Submit, poll, stream, restart-survival.

**Day 7 — write it up.** RESULTS.md and DECISIONS.md. This is not paperwork; it is
where you find out what you actually learned.

---

## 5. Rubric

Grade yourself honestly. The middle column is where most first attempts land.

| | Adequate | Good | Excellent |
|---|---|---|---|
| **Correctness** | Works on the happy path | Handles bad input and tool failure | Handles hostile input; fails safe |
| **Evals** | 30 cases, a number | Negative cases; a judge; a gate | Calibrated judge; CIs; regressions tracked over time |
| **Cost** | Tracked | Budgeted and capped | Measured per feature; an optimisation with before/after |
| **Observability** | Traces exist | Traces answer "where did it go wrong" | You debugged a real bug from a trace alone and wrote it up |
| **Security** | Default-deny permissions | Sandbox + HITL | You red-teamed it and closed a path you found |
| **Judgement** | Decisions recorded | Decisions justified | Decisions justified **with numbers**, including one you reversed |

---

## 6. When you are done

You have written, from scratch, the equivalent of an agent framework — and more
importantly, you know which parts of one you need.

**A good final exercise:** open the source of a framework you have heard of, find
its agent loop, and read it. It should take fifteen minutes and feel familiar. If
it does, the course worked.
