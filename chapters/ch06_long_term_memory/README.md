# Chapter 6 — Long-Term Memory

**Prerequisite:** Chapters 1–5 green. This is the longest chapter.

---

## After this chapter you can

- Explain what an embedding is and why cosine similarity is the right comparison
- Build a working vector store and know exactly when to stop using your own
- Chunk documents without destroying the facts inside them
- Distinguish semantic, episodic and procedural memory, and say why it matters
- Rank memories by relevance *and* recency *and* importance
- Decide what an agent should write down — the part everyone underestimates

> **⚠️ OpenRouter does not serve embeddings.** It proxies chat completions only. Every
> test in this chapter uses the built-in `HashingEmbedder` (free, offline,
> deterministic), which is enough to learn all the machinery. For the real exercise
> pick one: an OpenAI key with `text-embedding-3-small` ($0.02/M tokens), or
> `pip install sentence-transformers` and run `all-MiniLM-L6-v2` locally for nothing.
> The `Embedder` interface is the same either way.

---

## 1. The one idea

**Short-term memory is about a conversation. Long-term memory is about a user.**

Everything in Chapter 5 dies with the thread. This chapter is about facts that
shouldn't: who the user is, what was decided last month, how this team likes things
done.

The mechanism is always the same three steps:

```
  WRITE          text ──embed──► vector ──► store (with metadata)
  SEARCH        query ──embed──► vector ──► compare to all ──► top k
  USE                  top k ──► into the prompt ──► model answers
```

## 2. Embeddings

An embedding turns text into a list of numbers — a point in high-dimensional space —
positioned so that **texts with similar meaning are near each other**.

```
"my car broke down"      → [0.21, -0.88, 0.04, ... ]   (1536 numbers)
"my automobile failed"   → [0.19, -0.85, 0.07, ... ]   ← near
"the soup was delicious" → [-0.71, 0.33, 0.52, ... ]   ← far
```

Real embedding models learn this from enormous amounts of text. The learning is what
makes "car" and "automobile" close despite sharing no letters.

### Cosine similarity

To compare two vectors, measure the **angle** between them:

```
cos(a, b) = (a · b) / (|a| × |b|)
```

Range −1 to 1. In practice, with modern embedding models, expect 0 to 1.

**Why the angle and not the distance?** Cosine ignores magnitude. A two-sentence note
and a two-page essay about Postgres point in the same direction but have very
different lengths; Euclidean distance would call them dissimilar. You want them to
match.

**The optimisation everyone uses:** if you normalise every vector to length 1 when you
store it, then `|a| = |b| = 1` and cosine collapses to a plain dot product. No square
roots at query time. Every real vector database does this.

### What the scores actually mean

Do not attach meaning to absolute values — they vary by model, and this trips people
up constantly.

| Score | Roughly |
|---|---|
| > 0.85 | near-duplicate |
| 0.5–0.85 | genuinely related |
| 0.3–0.5 | loosely related |
| < 0.3 | probably unrelated |

**Calibrate on your own data.** Embed 20 pairs you know the answer for, look at the
numbers, and set your threshold from that. Copying a threshold from a blog post is how
you end up with a retriever that returns everything or nothing.

### The one argument people forget: `min_score`

```python
results = store.search(query, k=5)              # always returns 5
results = store.search(query, k=5, min_score=0.3)  # returns 0-5
```

With `k` alone, the nearest neighbour of *any* query is still something. Ask a
codebase index about medieval poetry and you get five confidently irrelevant files,
which the model will then cite. A floor lets the honest answer "nothing relevant" exist.

## 3. Chunking

You cannot embed a 50-page document as one vector — the meaning averages out into
mush, and retrieving it puts 50 pages in your context to answer one question.

So you split. Two parameters, and both matter:

**`max_chars` (500–1500 typical).** The chunk is the unit of retrieval. Too big
dilutes; too small loses meaning. A chunk should be able to answer a question on its
own.

**`overlap` (10–20% of max_chars).** Without it, a fact spanning a boundary is in
neither chunk:

```
...the timeout is set to        │  30 seconds in production...
        chunk 1 ends here ──────┘  └────── chunk 2 starts here
```

Neither chunk answers "what is the production timeout?" Overlap means at least one
contains the whole fact.

**Split on natural boundaries.** Prefer paragraph breaks, then lines, then sentences,
then words. Cutting mid-sentence produces chunks that embed badly, because half a
sentence means something different from the whole.

**Keep the source in metadata.** `{"source": "handbook.md", "section": "Deploys"}`.
Retrieval without provenance means the model cannot cite, and you cannot debug why a
bad chunk came back.

## 4. Three kinds of memory

Borrowed from cognitive psychology, kept because the distinction is operationally
useful:

| Kind | What | Example | Behaviour |
|---|---|---|---|
| **Semantic** | Timeless facts | "Akash works in fintech" | Gets **updated**, doesn't decay |
| **Episodic** | Things that happened | "On 14 Sep we chose Postgres" | **Accumulates**, decays with age |
| **Procedural** | How to do things | "Always run migrations before deploy" | Retrieved **by task**, doesn't decay |

Why not one undifferentiated pile? Because the three need different rules:

- A semantic fact that changes must **replace** its predecessor. If "works at Acme"
  and "works at Kryptos" both sit in the store, recall returns both and the model
  guesses.
- An episodic memory from three months ago should rank below one from yesterday.
- A procedural rule from a year ago is exactly as valid as one from today — decaying
  it would be wrong.

## 5. Ranking: similarity is not enough

Consider two stored memories and the query *"what colour do they like?"*:

```
"The user's favourite colour is blue"        similarity 0.82
"The user changed their mind, it's green"    similarity 0.79
```

Similarity ranks the stale one first. You need more terms:

```python
score = 0.6 * similarity
      + 0.2 * recency        # exponential decay, episodic only
      + 0.2 * importance     # assigned at write time
```

**Recency** as exponential decay with a half-life: `0.5 ** (age / half_life)`. Seven
days is a reasonable default for episodic memory. Semantic and procedural get 1.0 —
they don't age.

**Importance** set when writing. "The user's name is Akash" is a 0.9; "the user said
thanks" is a 0.1 and probably shouldn't be stored at all.

**Over-fetch before re-ranking.** Pull 3×k from the vector store, then apply the
composite score and cut to k. If you only re-rank what similarity already picked, the
recency and importance terms can never promote anything — they become decorative.

## 6. Writing: the part everyone gets wrong

Retrieval is the fun part. **What you write down decides whether retrieval works at
all**, and it is where real systems fail.

### Do not remember everything

An agent that writes a memory every turn ends up with a store that is 90% noise. Since
`k` is finite, noise crowds out signal: the useful fact is at rank 12 and never
retrieved. More memories makes it *worse*, not better.

### Write self-contained facts

```
BAD   "He prefers it"                       ← meaningless alone, and alone is how
BAD   "The user said yes"                     it will be retrieved
GOOD  "Akash prefers Python over JavaScript"
GOOD  "Akash approved the Postgres migration on 2026-09-14"
```

A memory is retrieved *without its conversation*. If it doesn't stand alone, it is
noise with extra steps.

### Deduplicate on write

Embed the candidate, search, and if the top hit is above ~0.95, don't store it. This
is a correctness feature, not an optimisation — without it you accumulate forty copies
of the user's name and every recall returns the same fact forty times.

### Update, don't append, for semantic facts

When a fact changes, replace it. Keeping both and hoping the model picks the newer one
is not a strategy.

### Forget

Real systems need a deletion policy, for quality and for law:
- **TTL** on episodic memories
- **Usage-based**: never retrieved in 90 days → drop
- **Explicit**: "forget that" must work, and under GDPR it must work properly
- **Consolidation**: merge many episodic memories into one semantic fact

## 7. When to stop using your own vector store

The one here is brute-force: compare the query to every vector, O(n) per query. Honest
numbers:

| Vectors | Query time | Verdict |
|---|---|---|
| 1,000 | ~2 ms | fine |
| 10,000 | ~20 ms | fine |
| 100,000 | ~200 ms | slow |
| 1,000,000 | ~2 s | no |

Past ~50k, move to an approximate index (HNSW, IVF) in a real store: **pgvector** if
you already have Postgres (usually the right answer), **Qdrant** or **LanceDB** if you
want purpose-built, **Chroma** for prototypes.

They expose the same `add` / `search` / `delete` interface you just built, which is
why building it first is worth the afternoon.

**One production footgun:** never mix vectors from two different embedding models in
one index. The numbers stay valid and the similarities become meaningless — no error,
just silently wrong retrieval. Store the model name and refuse a mismatch.

## 8. Common mistakes

1. **No `min_score`.** Confidently irrelevant results, every time.
2. **Copying a similarity threshold from the internet.** Calibrate on your data.
3. **Chunks with no overlap.** Facts on boundaries become unfindable.
4. **Chunking mid-sentence.** Half a sentence embeds as something else.
5. **No source metadata.** No citations, no debugging.
6. **Remembering everything.** Noise crowds out signal; more memory, worse recall.
7. **Memories that need context to make sense.** They will never have it.
8. **No deduplication.** Forty copies of one fact.
9. **Appending a changed fact instead of replacing it.** The model guesses.
10. **Ranking on similarity alone.** Stale facts outrank current ones.
11. **Re-ranking only the top-k.** Recency and importance become decorative.
12. **Mixing embedding models in one index.** Silent nonsense.
13. **Re-embedding the same text repeatedly.** Cache it; embeddings are deterministic.

## 9. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_similarity.py` | `l2_normalise`, `cosine_similarity`, `HashingEmbedder` |
| 2 | `exercise_2_vector_store.py` | `VectorStore` — add, search, filter, delete, persist |
| 3 | `exercise_3_chunking.py` | `chunk_text` — boundaries and overlap |
| 4 | `exercise_4_scoring.py` | `recency_weight`, `composite_score` |
| 5 | `exercise_5_memory_store.py` | `MemoryStore` — remember, dedup, recall, update, forget |
| 6 | `exercise_6_rag_agent.py` | **Integration:** an agent with memory across sessions |

```bash
pytest chapters/ch06_long_term_memory/tests -q
```

## 10. Check yourself

1. What is an embedding? Why cosine rather than Euclidean distance?
2. Why normalise vectors at write time?
3. What does `min_score` prevent, and what goes wrong without it?
4. Why is a similarity of 0.7 not interpretable across two different models?
5. Why overlap chunks? Draw the failure it prevents.
6. Name the three memory kinds, with an example and a decay rule for each.
7. Why does ranking on similarity alone return stale facts?
8. Why over-fetch 3×k before re-ranking?
9. Why does an agent that remembers everything have *worse* recall?
10. What makes a memory self-contained, and why must it be?
11. At what scale do you abandon this vector store, and what do you move to?
12. What happens if you mix two embedding models in one index?

---

**Next:** Chapter 6b (bonus) — retrieval that actually finds things: BM25, hybrid search,
reranking, and measuring recall. Or skip ahead to Chapter 7 — the agent stops reacting and starts planning: decomposition,
plan-execute, and self-critique.
