# Building AI Agents From Scratch — A Full Course

**You need:** an OpenRouter API key and Python 3.11+
**Philosophy:** build everything raw first, then map it onto industry frameworks

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

## The chapters

Each is: a long README, runnable examples, stubbed exercises, and tests.

| # | Chapter | You build | Tests |
|---|---|---|---|
| 1 | [The Agent Loop](chapters/ch01_agent_loop/) | Provider shim, conversation state, retries, cost tracking, streaming | 79 |
| 2 | [Tools & Function Calling](chapters/ch02_tools/) | Schema generation, tool registry, safe dispatch | 92 |
| 3 | [The ReAct Loop](chapters/ch03_react_loop/) | The real loop: stop conditions, parallel tools, traces | 76 |
| 4 | [Context Engineering](chapters/ch04_context/) | Budgets, group-aware trimming, compaction | 77 |
| 5 | [Short-Term Memory](chapters/ch05_short_term_memory/) | Durable sessions, memory strategies, the summarisation cost trap | 55 |
| 6 | [Long-Term Memory](chapters/ch06_long_term_memory/) | Embeddings, a vector store, chunking, memory ranking | 138 |
| 6b | [Retrieval Quality (Advanced RAG)](chapters/ch06b_retrieval/) | BM25, hybrid search with RRF, reranking, query rewriting, recall@k / MRR / nDCG | 139 |
| 7 | [Planning & Reflection](chapters/ch07_planning/) | Plans with dependencies, an executor, self-critique | 98 |
| 8 | [Multi-Agent Systems](chapters/ch08_multi_agent/) | Router, orchestrator/worker, blackboard — and the case against | 65 |
| 8b | [Agent Harness Patterns](chapters/ch08b_harness/) | Todo lists, skills (progressive disclosure), subagents, filesystem memory; reasoning models, multimodal, computer use | 106 |
| 9 | [Structured Output](chapters/ch09_structured_output/) | Extraction, a JSON Schema validator, repair loops, guardrails | 99 |
| 10 | [Evals I — The Harness](chapters/ch10_evals_basics/) | Datasets, checks, a parallel runner, CI gates | 90 |
| 11 | [Evals II — Judges](chapters/ch11_evals_judges/) | LLM judges, position-bias control, trajectories, statistics | 104 |
| 12 | [Observability](chapters/ch12_observability/) | Spans, a tracer, instrumentation by wrapping | 90 |
| 13 | [Production Hardening](chapters/ch13_hardening/) | Caching, circuit breaker, rate limiter, budget guard, idempotency | 82 |
| 13b | [Model Routing, Fallbacks & Cascades](chapters/ch13b_routing/) | Fallback chains, capability-based model selection, routers, cascades and their cost maths | 119 |
| 14 | [Security & Safety](chapters/ch14_security/) | Permissions, sandboxing, blast radius, human-in-the-loop | 81 |
| 15 | [Serving & Scale](chapters/ch15_serving/) | SSE, a job queue, durable runs, async | 73 |
| 16 | [MCP](chapters/ch16_mcp/) | JSON-RPC, an MCP server and client, the tool bridge | 94 |
| 17 | [Frameworks, Decoded](chapters/ch17_frameworks/) | A state graph in 150 lines — i.e. most of LangGraph | 77 |
| 18 | [Capstone](chapters/ch18_capstone/) | One real agent, with everything, measured | 43* |

<sub>*the capstone suite checks your project's structure; it skips until you set `CAPSTONE_PATH`.</sub>

6b, 8b and 13b are optional deep-dives. Do them right after the chapter they follow;
nothing later depends on them.

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
Agentic-course/
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

1. **Read the README end to end, without coding.**
2. **Run every file in `examples/`.** Change a number, run it again, see what breaks.
3. **Do the exercises in order.** `pytest chapters/chNN_name/tests -q` until green.
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
flakes. The whole course costs roughly **$3–15** in API spend, all of it from the
integration exercises you run by hand.

---

## Progress

- [ ] Ch 1 — The Agent Loop
- [ ] Ch 2 — Tools & Function Calling
- [ ] Ch 3 — The ReAct Loop
- [ ] Ch 4 — Context Engineering
- [ ] Ch 5 — Short-Term Memory
- [ ] Ch 6 — Long-Term Memory
- [ ] Ch 6b — Retrieval Quality
- [ ] Ch 7 — Planning & Reflection
- [ ] Ch 8 — Multi-Agent Systems
- [ ] Ch 8b — Agent Harness Patterns
- [ ] Ch 9 — Structured Output & Reliability
- [ ] Ch 10 — Evals I: The Harness
- [ ] Ch 11 — Evals II: Judges & Statistics
- [ ] Ch 12 — Observability & Tracing
- [ ] Ch 13 — Production Hardening
- [ ] Ch 13b — Model Routing, Fallbacks & Cascades
- [ ] Ch 14 — Security & Safety
- [ ] Ch 15 — Serving & Scale
- [ ] Ch 16 — MCP
- [ ] Ch 17 — Frameworks, Decoded
- [ ] Ch 18 — Capstone
