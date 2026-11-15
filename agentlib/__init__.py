"""agentlib — the agent framework you are building, one chapter at a time.

This package is the REFERENCE implementation. Each chapter's `exercises/` ask you to
build your own version of a piece of it; `agentlib` holds the finished article so that
every later chapter has something working to import.

Using it to check your answer is fine. Using it *instead* of doing the exercise means
Chapter 13 will find you out.

Layout:
    errors             ch1   the error hierarchy everything raises
    llm                ch1   provider shim over OpenRouter
    tokens             ch1   local token estimation
    conversation       ch1   message history with a protected system prompt
    retry              ch1   backoff + jitter
    cost               ch1   spend tracking and budgets
    streaming          ch1   token-by-token output
    pricing            ch1   $/M token table
    testing            ch1   fakes, so tests are free and offline
    tools              ch2   schemas from signatures, registry, safe dispatch
    agent              ch3   the loop, stop conditions, traces
    context            ch4   budgets, group-aware trimming, compaction
    memory.short_term  ch5   session stores and memory strategies
    embeddings         ch6   embedders and cosine similarity
    memory.vector      ch6   a vector store and chunking
    memory.long_term   ch6   memory kinds, ranking, extraction
    retrieval          ch6b  BM25, hybrid search (RRF), reranking, retrieval metrics
    planning           ch7   plans, dependencies, executor, reflection
    multiagent         ch8   blackboard, router, orchestrator
    harness            ch8b  todos, skills, subagents, sandboxed workspace
    structured         ch9   extraction, validation, repair, guardrails
    evals.core         ch10  datasets, checks, runner, reports
    evals.judge        ch11  LLM judges, trajectories, statistics
    tracing            ch12  spans, tracer, instrumentation wrappers
    hardening          ch13  cache, breaker, rate limit, budget, idempotency
    routing            ch13b fallback chains, model selection, routers, cascades
    security           ch14  permissions, sandboxing, detection, approvals
    server             ch15  SSE, run store, job queue, async helpers
    mcp.protocol/server/client  ch16  JSON-RPC and the tool bridge
    graph              ch17  a state graph in ~150 lines
"""

__version__ = "0.1.0"
