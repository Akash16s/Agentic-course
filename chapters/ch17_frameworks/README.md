# Chapter 17 — Frameworks, Decoded

**Time: ~6 hours** (50 min reading · 30 min examples · 3.5 hrs exercises · 1 hr review)
**Prerequisite:** Chapters 1–16 green.

---

## After this chapter you can

- Map every framework concept onto something you have already written
- Build a state graph — most of what LangGraph is — in about 150 lines
- Read framework source instead of framework docs, and know when the docs are lying
- Decide, with reasons, whether to adopt one

---

## 1. The one idea

**You have already built all of it.**

| Framework concept | What it is | Your chapter |
|---|---|---|
| `AgentExecutor` / `create_react_agent` | the loop | 3 |
| `@tool` / `StructuredTool.from_function` | signature → JSON Schema | 2 |
| `ConversationBufferMemory` | a message list | 1, 5 |
| `ConversationSummaryBufferMemory` | compaction + a cache | 4, 5 |
| `VectorStoreRetriever` | cosine search + top-k | 6 |
| `StateGraph` | nodes, edges, a state dict | **this chapter** |
| Checkpointer | serialise state between steps | 15 |
| Handoffs / swarm | pass control, carry context | 8 |
| Guardrails | validate and repair output | 9 |
| Tracing / LangSmith | spans in a tree | 12 |
| Evaluators | checks over a dataset | 10, 11 |

There is no row you cannot fill in. That is the entire point of having built it
yourself, and it is why this chapter comes last rather than first.

## 2. A state graph in 150 lines

LangGraph's core model, in full:

- **State** — a dict passed between nodes
- **Nodes** — functions `state -> partial update`
- **Edges** — unconditional (`a` always goes to `b`)
- **Conditional edges** — a router function picks the next node
- **Reducers** — how an update merges into existing state

That is it. `agentlib/graph.py` implements all five.

### Partial updates and reducers

A node returns only the keys it changed:

```python
def think(state):
    return {"messages": "a thought", "steps": 1}
```

The *reducer* decides how that merges:

```python
StateGraph({"messages": append, "steps": add})
```

Without `append`, every node touching `messages` would have to read the list, copy
it, append and return the whole thing — and any node that forgot would silently wipe
the conversation. That single design decision is why the pattern exists, and it is
worth understanding before you use it.

### Chapter 3's loop, as a graph

```python
graph.set_entry("think")
graph.add_conditional_edges("think", route, {"act": "act", "done": END})
graph.add_edge("act", "think")
```

Which produces `think → act → think → act → think → END`. Compare that to your
twelve-line `while` loop and ask what you gained:

- **You can draw it.** `to_mermaid()` is honestly most of the appeal.
- **You can validate it.** Unreachable nodes and dangling edges become errors at
  compile time instead of hangs at runtime.
- **You can checkpoint between nodes**, which makes a run resumable (Chapter 15).
- **You can stream steps** for free.

And what you paid: indirection, a new vocabulary, and a bug surface that is now
partly someone else's.

### Validation is the real feature

```
node 'summarise' has no outgoing edge; it would stall the graph
router at 'think' returned 'retry', which is not in ['act', 'done']
```

Every one of those failures, in a hand-rolled loop, presents as a hang or a KeyError
three steps later. Catching them at `compile()` is a genuine win — and it is
fifty lines you could also write yourself, which is the honest summary of this whole
chapter.

### It still needs a step limit

A graph with a cycle and a router that never returns "done" is Chapter 3's infinite
loop wearing a diagram. `max_steps` does not become optional because you drew a
picture.

## 3. The landscape, honestly

**LangGraph** — the graph model above, plus checkpointers, human-in-the-loop
interrupts and a hosted platform. The strongest choice if you want durable,
resumable, inspectable workflows. Heavier than it looks, and the LangChain
dependency brings a lot with it.

**OpenAI Agents SDK** — deliberately small: agents, handoffs, guardrails, sessions,
tracing. Reads like Chapter 8 with a nicer API. Easy to adopt, easy to drop.

**Claude Agent SDK** — the loop behind Claude Code, exposed. Strong on tools,
permissions and MCP; opinionated about the loop, which is a feature if you agree
with the opinions.

**CrewAI** — role-playing agents ("researcher", "writer"). Demos beautifully.
Re-read Chapter 8 §1 before you commit to it.

**Pydantic AI** — types and validation first. If Chapter 9 was your favourite
chapter, this is your framework.

**Nothing at all** — for a single-purpose agent, your `agentlib` is a genuinely
reasonable answer. Plenty of production agents are a few hundred lines of exactly
this.

## 4. Should you adopt one?

**Yes, if** — you want durable execution and don't want to build it; you need
human-in-the-loop interrupts mid-graph; your team already knows one; you want a
hosted tracing UI without wiring it up; you are shipping next week.

**No, if** — your agent is one loop and five tools; you need precise control over
context and cost; you need to debug deeply (frameworks make stack traces much
worse); the abstraction is fighting you rather than helping.

**The honest middle:** use a framework for the plumbing you don't care about and
keep your own code for the parts that make your agent yours — which is usually the
prompt, the tools and the evals, none of which a framework helps with much.

## 5. How to read framework source

You now can, and it is faster than the docs.

1. **Find the loop.** Search for `while`, `for step in`, or `astream`. Everything
   else is decoration around it.
2. **Find the message construction.** What actually goes in the context window? This
   is where frameworks surprise you — hidden system prompts, injected examples,
   reformatted tool results.
3. **Find the stop conditions.** Is there a step limit? A cost limit? Often not.
4. **Find the error handling.** What happens on a 429? On a tool exception?
5. **Find where `tools=` is built.** Compare it with your Chapter 2 schema generator.

If you cannot answer #2 for a framework, do not put it in production. You cannot
control cost or quality without knowing what is in the window.

## 6. Common mistakes

1. **Adopting a framework before you can name the problem it solves.**
2. **Assuming the docs describe the current behaviour.** Read the source.
3. **Not knowing what goes in your own context window.**
4. **Using a graph for a straight line.** A function call is a fine abstraction.
5. **Forgetting `max_steps` because the graph has a diagram.**
6. **Forgetting reducers, then losing state.** Every node overwrites `messages`.
7. **Believing role-play makes agents better.** Chapter 8.
8. **Rewriting your evals in framework terms.** Keep them outside; they must
   survive the framework.
9. **Framework lock-in on the parts that matter.** Keep the prompts, tools and evals
   yours.

## 7. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_reducers.py` | `replace`, `append`, `add` — state merging |
| 2 | `exercise_2_graph.py` | `StateGraph` — nodes, edges, routers, validation |
| 3 | `exercise_3_execution.py` | `CompiledGraph.stream` / `invoke` |
| 4 | `exercise_4_port.py` | Port Chapter 3's agent loop onto the graph |
| 5 | `exercise_5_compare.py` | **Integration:** the same agent, three ways, measured |

```bash
pytest chapters/ch17_frameworks/tests -q
```

## 8. Check yourself

1. Name five framework concepts and the chapter where you built each.
2. What are the five parts of a state graph?
3. Why do nodes return partial updates rather than whole state?
4. What does the `append` reducer prevent?
5. What does `compile()` catch, and how would each failure present without it?
6. Does a graph remove the need for a step limit? Why not?
7. Name three things a graph buys you over a `while` loop, and two it costs.
8. Give one situation where LangGraph is clearly right, and one where it clearly isn't.
9. The five things to look for when reading framework source. Which is
   non-negotiable before production?
10. Which parts of your agent should stay yours whatever framework you adopt?

---

**Next:** Chapter 18 — the capstone. Everything, on one real problem.
