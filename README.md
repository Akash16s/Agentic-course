# Building AI Agents From Scratch — A Full Course

**Your setup:** OpenRouter API key · Python 3.11 · comfortable with Python, some backend
**Your pace:** 10–15 hrs/week
**Philosophy:** build everything raw first, then map it onto industry frameworks

**Status: all 18 chapters of Track A are written, plus 3 bonus chapters (6b, 8b, 13b).
1,834 tests pass.**

---

## What this is

You build a production-grade agent framework **from nothing**. No LangGraph, no
CrewAI, no magic — Python, HTTP calls, and a clear head. By the end you will have
written your own version of every piece the big frameworks give you, and you will
know which of those pieces you actually need.

**Why raw first?** Frameworks hide the loop. People who learn LangGraph first can
build a demo in an afternoon and then cannot debug it, cannot cost-optimise it, and
cannot say why their agent went into a tool-call spiral. People who build the loop
themselves pick up any framework in a day. Chapter 17 is where you collect on that.

---

## The three tracks

| Track | What it teaches | Hours | Weeks @ 12h/wk |
|---|---|---|---|
| **A — AI Agents** ✅ written | Building, evaluating and shipping agents | ~127 | ~11 |
| **B — Deep Learning** (outline) | How the model works, tensors to a trained transformer | ~140 | ~12 |
| **C — AI Inference** (outline) | How models are served fast and cheap at scale | ~55 | ~5 |
| **Total** | | **~322** | **~27 weeks (~6 months)** |

`assignment1-basics` (Stanford CS336) is already sitting next door — that becomes the
spine of Track B. Track C only fully makes sense after Track B.

---

## Track A — the chapters

Each is: a long README, runnable examples, stubbed exercises, and tests.

| # | Chapter | You build | Hrs | Tests |
|---|---|---|---|---|
| 1 | [The Agent Loop](chapters/ch01_agent_loop/) | Provider shim, conversation state, retries, cost tracking, streaming | 5 | 79 |
| 2 | [Tools & Function Calling](chapters/ch02_tools/) | Schema generation, tool registry, safe dispatch | 6 | 92 |
| 3 | [The ReAct Loop](chapters/ch03_react_loop/) | The real loop: stop conditions, parallel tools, traces | 6 | 76 |
| 4 | [Context Engineering](chapters/ch04_context/) | Budgets, group-aware trimming, compaction | 5 | 77 |
| 5 | [Short-Term Memory](chapters/ch05_short_term_memory/) | Durable sessions, memory strategies, the summarisation cost trap | 5 | 55 |
| 6 | [Long-Term Memory](chapters/ch06_long_term_memory/) | Embeddings, a vector store, chunking, memory ranking | 8 | 138 |
| 6b | [Retrieval Quality (Advanced RAG)](chapters/ch06b_retrieval/) ★ | BM25, hybrid search with RRF, reranking, query rewriting, recall@k / MRR / nDCG | 6 | 139 |
| 7 | [Planning & Reflection](chapters/ch07_planning/) | Plans with dependencies, an executor, self-critique | 6 | 98 |
| 8 | [Multi-Agent Systems](chapters/ch08_multi_agent/) | Router, orchestrator/worker, blackboard — and the case against | 6 | 65 |
| 8b | [Agent Harness Patterns](chapters/ch08b_harness/) ★ | Todo lists, skills (progressive disclosure), subagents, filesystem memory; reasoning models, multimodal, computer use | 6 | 106 |
| 9 | [Structured Output](chapters/ch09_structured_output/) | Extraction, a JSON Schema validator, repair loops, guardrails | 4 | 99 |
| 10 | [Evals I — The Harness](chapters/ch10_evals_basics/) | Datasets, checks, a parallel runner, CI gates | 6 | 90 |
| 11 | [Evals II — Judges](chapters/ch11_evals_judges/) | LLM judges, position-bias control, trajectories, statistics | 6 | 104 |
| 12 | [Observability](chapters/ch12_observability/) | Spans, a tracer, instrumentation by wrapping | 5 | 90 |
| 13 | [Production Hardening](chapters/ch13_hardening/) | Caching, circuit breaker, rate limiter, budget guard, idempotency | 6 | 82 |
| 13b | [Model Routing, Fallbacks & Cascades](chapters/ch13b_routing/) ★ | Fallback chains, capability-based model selection, routers, cascades and their cost maths | 5 | 119 |
| 14 | [Security & Safety](chapters/ch14_security/) | Permissions, sandboxing, blast radius, human-in-the-loop | 5 | 81 |
| 15 | [Serving & Scale](chapters/ch15_serving/) | SSE, a job queue, durable runs, async | 8 | 73 |
| 16 | [MCP](chapters/ch16_mcp/) | JSON-RPC, an MCP server and client, the tool bridge | 5 | 94 |
| 17 | [Frameworks, Decoded](chapters/ch17_frameworks/) | A state graph in 150 lines — i.e. most of LangGraph | 6 | 77 |
| 18 | [Capstone](chapters/ch18_capstone/) | One real agent, with everything, measured | 12 | 43* |

<sub>*the capstone suite checks your project's structure; it skips until you set `CAPSTONE_PATH`.</sub><br>
<sub>★ bonus chapters: do them right after the chapter they follow. They fill gaps every
production agent team hits, but nothing later depends on them.</sub>

### Calendar at 12 hrs/week

Week 1: ch 1–2 · Week 2: ch 3–4 · Week 3: ch 5–6 · Week 4: ch 6b–7 · Week 5: ch 8–8b
Week 6: ch 9–10 · Week 7: ch 11–12 · Week 8: ch 13–13b · Week 9: ch 14–15
Week 10: ch 16–17 · Week 11: ch 18

---

## Start here

```bash
cd Agentic-course    # wherever you cloned it
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env               # paste your OpenRouter key

python chapters/ch01_agent_loop/examples/00_check_setup.py   # verify + list models
open chapters/ch01_agent_loop/README.md                      # then read this
```

**Model ids change.** Run `00_check_setup.py` before trusting the default in `.env`.

---

## Layout

```
Agentic Course/
├── README.md · SETUP.md
├── agentlib/                  THE REFERENCE LIBRARY — the finished article
│   ├── errors llm tokens conversation retry cost streaming pricing testing   (ch 1)
│   ├── tools agent context                                              (ch 2-4)
│   ├── memory/short_term memory/vector memory/long_term embeddings      (ch 5-6)
│   ├── retrieval                                                        (ch 6b)
│   ├── planning multiagent harness structured                           (ch 7-9)
│   ├── evals/core evals/judge tracing hardening routing security        (ch 10-14)
│   └── server mcp/ graph                                                (ch 15-17)
└── chapters/chNN_name/
    ├── README.md     the chapter — read this first, without coding
    ├── examples/     runnable, mostly free and offline. Run them, break them.
    ├── exercises/    stubs with TODOs. This is the real work.
    ├── tests/        pytest. Offline, deterministic, $0.
    └── solutions/    after you've tried. Seriously.
```

**`agentlib` is the reference implementation, and every chapter's exercises ask you
to rebuild a piece of it.** It exists so later chapters always have something working
to import. Checking your answer against it is fine; skipping the exercise is how
Chapter 13 catches you out.

---

## The rhythm for each chapter

1. **Read the README end to end, without coding.** ~45 min.
2. **Run every file in `examples/`.** Change a number, run it again, see what breaks.
3. **Do the exercises in order.** `pytest chapters/chNN_name/tests -q` until green.
   This is ~60% of your time.
4. **Answer the "Check yourself" questions from memory.**
5. Move on. Do not start chapter N+1 until N is green — they compound hard.

```bash
pytest chapters/ch01_agent_loop/tests -q            # one chapter
pytest chapters/ch01_agent_loop/tests -q -k tokens  # one exercise
pytest chapters -q                                  # everything
./run_tests.sh 6b                                   # helper; accepts bonus chapter ids
./run_tests.sh --solutions 6b                       # same, against the solutions
```

Every test runs **offline against fakes**. `pytest` never costs a cent and never
flakes. The whole of Track A costs roughly **$3–15** in API spend, all of it from the
integration exercises you run by hand.

---

## Progress

- [ ] Ch 1 — The Agent Loop
- [ ] Ch 2 — Tools & Function Calling
- [ ] Ch 3 — The ReAct Loop
- [ ] Ch 4 — Context Engineering
- [ ] Ch 5 — Short-Term Memory
- [ ] Ch 6 — Long-Term Memory
- [ ] Ch 6b — Retrieval Quality (bonus)
- [ ] Ch 7 — Planning & Reflection
- [ ] Ch 8 — Multi-Agent Systems
- [ ] Ch 8b — Agent Harness Patterns (bonus)
- [ ] Ch 9 — Structured Output & Reliability
- [ ] Ch 10 — Evals I: The Harness
- [ ] Ch 11 — Evals II: Judges & Statistics
- [ ] Ch 12 — Observability & Tracing
- [ ] Ch 13 — Production Hardening
- [ ] Ch 13b — Model Routing, Fallbacks & Cascades (bonus)
- [ ] Ch 14 — Security & Safety
- [ ] Ch 15 — Serving & Scale
- [ ] Ch 16 — MCP
- [ ] Ch 17 — Frameworks, Decoded
- [ ] Ch 18 — Capstone

---

## Track B — Deep Learning (outline, later)

Tensors & autograd from scratch → backprop by hand → MLPs & optimisation → BPE
tokenisation → the transformer from scratch (**CS336 A1**, already next door) →
training loops, mixed precision, checkpointing → distributed training (A2) → data
curation → scaling laws → fine-tuning and LoRA → alignment: SFT, DPO, RLHF (A5).

## Track C — AI Inference (outline, later)

What generation actually costs → the KV cache → prefill vs decode → static, dynamic
and continuous batching → PagedAttention and vLLM → quantisation (GPTQ/AWQ/FP8) →
speculative decoding → constrained decoding → GPU memory maths → benchmarking (TTFT,
TPOT, throughput) → autoscaling and cost per million tokens.

Several forward references in Track A point here — why inference is not bit-reproducible
(ch 11), why output length dominates latency (ch 1), how constrained decoding makes
structured output exact (ch 9).
