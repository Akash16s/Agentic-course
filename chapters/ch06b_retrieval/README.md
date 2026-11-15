# Chapter 6b — Retrieval Quality (Advanced RAG)

**Prerequisite:** Chapter 6 green. This is a bonus chapter: Chapter 7 does not depend on
it, but every agent you build that reads documents does.

---

## After this chapter you can

- Say exactly why vector search misses error codes and keyword search misses synonyms
- Implement BM25 from scratch and explain what every term in it is for
- Merge two rankings with Reciprocal Rank Fusion, and say why adding scores is wrong
- Rerank a wide candidate list with a model, without letting a bad reply break search
- Rewrite queries before searching — including "what about the second one?"
- Measure retrieval on its own with recall@k, MRR and nDCG over a golden set
- Decide when to stop building this yourself and use Postgres, Elastic or a hosted reranker

> **⚠️ Offline, like Chapter 6.** The tests use `HashingEmbedder`, which only sees
> words, not meaning. Exercise 5 adds a tiny `ToySemanticEmbedder` that fakes two
> habits of real embedding models (synonyms land close together; identifiers get
> blurred) so you can see hybrid search win without an embeddings key. The reranker
> and query rewriting need a chat model, and **those work with your OpenRouter key**.
> The tests use `FakeLLMClient`, so `pytest` stays free.

---

## 1. The one idea

**Retrieval is the ceiling on answer quality.**

If the passage that answers the question is not in the context, no model can use
it. The best case is the model says "I don't know". The usual case is it makes
something up that sounds right.

So when a RAG system gives a bad answer, the first question is not "how do I fix
the prompt?" It is "**was the right passage retrieved at all?**" On most systems,
most of the time, it wasn't.

Chapter 6 retrieved with one tool: embed the query, take the top k by cosine. This
chapter turns that into the pipeline real systems use:

```
                      ┌─► vector search (top 50) ─┐
  query ─► rewrite ─► ┤                           ├─► fuse (RRF) ─► rerank ─► top 5 ─► model
                      └─► BM25 keyword (top 50) ──┘    by rank      by model
                                                                       │
                       measure HERE, before the model ◄────────────────┘
                       (recall@k, MRR — free, fast, deterministic)
```

Every box is optional, and each one costs something. Measuring is how you find out
which ones pay for themselves on *your* data.

## 2. Why one kind of search is never enough

### Where vector search fails

Run `examples/01_where_vectors_fail.py`. A support agent is asked about error code
`E4012`. Vector search puts five documents in its top 5 and the answer is not one
of them. BM25 puts the answer first.

Two reasons, and a real embedding model has both:

1. **No sense of rarity.** "error" is in half the documents. "E4012" is in one.
   An embedding blends the query into one point and gives no extra weight to the
   rare word that actually matters.
2. **Identifiers get blurred.** Embedding models split `E4012` into sub-word pieces
   (`E`, `40`, `12`) and learn that it is "some error code". To them, `E4012` and
   `E4013` are nearly the same — but they are different problems with different
   fixes.

| Query contains | Example | Vector | Keyword (BM25) |
|---|---|---|---|
| Error codes, IDs | `E4012`, `INV-20931`, `0x80070005` | ✗ blurs them | ✓ |
| Names | "Shah" vs "Sharma", product `T2` | ✗ | ✓ |
| Versions, numbers | "Postgres 15" vs "Postgres 16" | ✗ | ✓ |
| Rare jargon | `idempotency-key`, `SIGTERM` | ~ | ✓ |
| Synonyms | "money back" → "refund" | ✓ | ✗ no shared word |
| Paraphrase | "can't log in" → "authentication failure" | ✓ | ✗ |
| Typos | "recieve" → "receive" | ~ | ✗ |
| Other languages | "remboursement" → "refund" | ✓ (multilingual models) | ✗ |

### Where keyword search fails

The reverse, in the same example: *"when do I get my money back?"* The document says
"refund". No shared word, so BM25 cannot find it. A model that has learned "money
back" and "refund" mean the same thing puts it first.

### So: hybrid

Run both and merge the results. Each covers the other's blind spot, and this is now
the default in production RAG — Elasticsearch, OpenSearch, Weaviate, Qdrant and
Postgres setups all offer it. It is cheap: BM25 over 100,000 chunks takes
milliseconds and needs no model.

## 3. BM25 from scratch

BM25 is the scoring function behind Lucene, Elasticsearch, OpenSearch and most
search boxes you have ever typed into. It is 30 years old and still very hard to beat
on keyword queries.

```
score(D, Q) = Σ over terms t in Q of

              IDF(t)  ×        tf × (k1 + 1)
                         ───────────────────────────────
                         tf + k1 × (1 − b + b × |D| / avgdl)

IDF(t)      = ln(1 + (N − n + 0.5) / (n + 0.5))
```

`tf` = times t appears in document D · `|D|` = D's length in words · `avgdl` = the
average length · `N` = number of documents · `n` = documents containing t.

That looks like a lot. It is three simple ideas multiplied together.

### Idea 1 — rare words matter more (IDF)

A word in every document tells you nothing. A word in one document tells you a lot.

| Term in n of 1,000 docs | IDF (smoothed, used here) | IDF (original) |
|---|---|---|
| 1 | 6.50 | 6.50 |
| 10 | 4.56 | 4.55 |
| 500 | 0.69 | 0.00 |
| 900 | 0.11 | **−2.19** |
| 1,000 | 0.00 | **−7.60** |

The original formula goes **negative** once a term is in more than half the
documents. A negative IDF means matching a common word makes a document rank
*lower* than not matching it. The `1 +` inside the log fixes that; it is what
Lucene uses, and what you will implement.

### Idea 2 — the tenth mention adds little (tf saturation, k1)

A document that says "refund" once is probably about refunds. One that says it ten
times is not ten times more about refunds. With `k1 = 1.5` and an average-length
document, the tf part grows like this:

| tf | 1 | 2 | 3 | 5 | 10 | 20 | ∞ |
|---|---|---|---|---|---|---|---|
| tf part | 1.00 | 1.43 | 1.67 | 1.92 | 2.17 | 2.33 | 2.5 (= k1+1) |

It can never pass `k1 + 1`. Keyword stuffing stops paying almost at once. `k1 = 0`
ignores tf completely (matched or not); bigger k1 lets tf count for longer.
Typical range: 1.2–2.0.

### Idea 3 — long documents match everything a bit (length normalisation, b)

A 5,000-word page mentions "refund" a few times by accident. The `|D| / avgdl` part
discounts tf for longer-than-average documents. `b = 0.75` is the standard; `b = 0`
turns it off; `b = 1` applies it fully.

### A worked example

Three documents, after `tokenise` drops stopwords like "the" and "was":

```
d1  reset your password from the login page             → 4 tokens
d2  error E4012 means the card was declined              → 5 tokens
d3  card payments fail when the card has expired
    or the card is blocked                               → 7 tokens   avgdl = 16/3 = 5.33
```

Query: **"card declined"**.

```
IDF(card)     = ln(1 + (3 − 2 + 0.5) / (2 + 0.5)) = ln(1.6)  = 0.470   (in 2 of 3)
IDF(declined) = ln(1 + (3 − 1 + 0.5) / (1 + 0.5)) = ln(2.67) = 0.981   (in 1 of 3)

d2: |D|/avgdl = 5/5.33 = 0.94
    length part = 1.5 × (1 − 0.75 + 0.75 × 0.94) = 1.43
    card        0.470 × (1 × 2.5) / (1 + 1.43) = 0.484
    declined    0.981 × (1 × 2.5) / (1 + 1.43) = 1.009
                                         total = 1.493

d3: |D|/avgdl = 7/5.33 = 1.31
    length part = 1.5 × (1 − 0.75 + 0.75 × 1.31) = 1.85
    card        0.470 × (3 × 2.5) / (3 + 1.85) = 0.727     ← says "card" 3 times
                                         total = 0.727

d1: no query terms                       total = 0  (not returned at all)
```

d3 says "card" three times and still scores half of d2: tf saturated, d3 is longer
than average, and d2 matched the rarer word. Your implementation must reproduce
1.493 and 0.727 — there is a test for it.

### Two things BM25 does that vectors don't

- **It can return nothing.** If no document contains a query word, the result is
  empty. Vector search always returns its k nearest, however far away they are.
- **It is only as good as its tokeniser.** `tokenise` does not stem, so "errors" does
  not match "error" (there is a test that shows this). Real engines run an
  *analyser* — lowercasing, stemming, sometimes synonyms — before indexing. When
  keyword search "mysteriously" misses, look at the tokens first.

## 4. Fusion: merge rankings, not scores

You now have two ranked lists. How do you merge them?

### The wrong way: add the scores

Run `examples/02_fusion_by_hand.py`:

```
rank  BM25            vector
1     kb-02  11.84    kb-06 0.83
2     kb-01   4.10    kb-01 0.81
3     kb-03   3.95    kb-05 0.79
4     kb-05   2.71    kb-02 0.77
```

BM25 scores are unbounded; cosine sits between −1 and 1. Add them and BM25 decides
everything — the vector list is a rounding error. Min-max normalising each list to
[0, 1] looks like a fix but is fragile: it stretches the vector list's tiny 0.77–0.83
spread into 0–1, and BM25's one big score squashes the rest of its list to about
0.15 or less.
**Scores from different systems are not on the same scale. Ranks are.**

### Reciprocal Rank Fusion (RRF)

```
fused(d) = Σ over lists of   weight / (k + rank of d in that list)        k = 60
```

```
doc     bm25 rank  vector rank
kb-01           2            2   1/62 + 1/62   = 0.0323   ← in both lists, wins
kb-02           1            4   1/61 + 1/64   = 0.0320
kb-05           4            3   1/64 + 1/63   = 0.0315
kb-06           -            1   1/61          = 0.0164   ← top of one list only
kb-03           3            -   1/63          = 0.0159
```

**Why k = 60?** With k = 60, rank 1 is worth 1/61 = 0.0164 and rank 10 is worth
1/70 = 0.0143 — not much difference. So "found by both retrievers" beats "first in
one of them". With k = 0, rank 1 is worth 1.0 and rank 2 only 0.5, and each list's
top pick dominates. 60 comes from the original paper (Cormack, Clarke & Büttcher,
2009). It is still the default almost everywhere, and rarely worth tuning.

**Weights** are the knob worth tuning. Code search full of identifiers: weight BM25
up. A help centre full of paraphrased questions: weight vectors up. Tune against a
golden set (section 8), never by feel.

**Fetch deep, return shallow.** Fusion can only promote documents that one of the
lists returned. If BM25 has the answer at rank 30 and you only asked each side for
10, fusion never sees it. Fetch ~50 from each side, return the top few.

RRF does not care where the lists came from: two retrievers, three phrasings of the
query (section 6), or both. One function, many uses.

## 5. Reranking: retrieve wide, rerank narrow

### Two ways to compare a query and a passage

```
BI-ENCODER (embeddings, Chapter 6)              CROSS-ENCODER (reranker)

  query ──► model ──► vector ─┐                 [query + passage] ──► model ──► 0.93
                              ├─► cosine
passage ──► model ──► vector ─┘

passages embedded ONCE, at index time           every (query, passage) pair is a
query time: one embed + a fast search           full model call, AT QUERY TIME
```

The bi-encoder never sees the query and the passage *together*. It compresses each
into one point, separately, and hopes the geometry works out. The cross-encoder reads
both at once, so it can notice that the passage says "E4013" and the query says
"E4012", or that the passage says "does *not* support refunds".

That makes cross-encoders much more accurate, and much too slow to run over a
corpus — you would make a model call for every document on every query. Hence the
standard shape:

```
  1,000,000 chunks ──(fast, bi-encoder + BM25)──► 50 candidates ──(slow, accurate)──► 5
```

### Your options

| Reranker | Latency for ~50 passages | Cost | Notes |
|---|---|---|---|
| None | 0 | 0 | Fine when recall@5 is already high |
| Local cross-encoder (e.g. `bge-reranker`) | ~100–500 ms on CPU, less on GPU | free | Needs `sentence-transformers` |
| Hosted reranker (Cohere, Voyage, Jina) | ~100–400 ms | ~$1–2 per 1,000 searches | Purpose-built, the usual production choice |
| **LLM as reranker** (Exercise 4) | ~1–3 s, one call | ~5k input tokens per query | Works with only an OpenRouter key; the most flexible |

Numbers are rough and change monthly. Measure your own.

### Making an LLM reranker safe

- **Number passages by position** (`[0]`, `[1]`...) not by doc id. Short numbers are
  cheap, and models copy them back correctly; long ids get mangled.
- **Truncate each passage.** Fifty full documents will blow your context budget and
  your bill.
- **Parse defensively.** Fenced JSON, prose around it, a missing wrapper, scores as
  strings, a passage number that does not exist — all normal.
- **Fail open.** Reranking improves an order you already have. Garbage reply or an
  API error → return the original order and count a `fallback`. Never fail the user's
  request over an optimisation. Then *alert on the fallback count*: a reranker that
  silently fell back on every call for a week looks exactly like one that works.
- **Watch position bias.** LLMs favour passages near the start of a list (Chapter 11
  measures this for judges). Your candidates arrive in fused order, which is mostly
  fine — but it means the reranker's job is harder for a good document at rank 40.

## 6. Query transformation: fix the question before searching

Users do not type queries the way documents are written. Four fixes, cheapest
first:

**Query rewriting.** `"hey so my card thing says E4012?? what do"` → `"E4012 card
declined meaning"`. One cheap model call. Useful when queries are chatty.

**Multi-query expansion.** Generate 3 phrasings, search with each, fuse the rankings
with RRF. Finds documents that any single phrasing misses. Costs one model call
plus 3× the searches. **Keep the original query in the set** — a bad rewrite must
never lose what the user actually typed.

**HyDE (Hypothetical Document Embeddings).** Ask the model to *write a plausible
answer*, then embed that and search with it. It works because answers look more like
documents than questions do. Two warnings: the fake answer can contain invented
specifics that pull in the wrong documents, and it does nothing for BM25 on
identifiers. Try it last, measure it, keep it only if it wins.

**Conversational rewriting.** The one chat agents cannot skip:

```
user:      compare the Starter and Pro plans
assistant: Starter is $10/month. Pro is $30/month with SSO...
user:      what about the second one's limits?
```

Embed "what about the second one's limits?" and you get a vector for "limits" in
general. Rewrite it first using the conversation — `"Pro plan usage limits"` — and
it retrieves. Skip the model call when there is no history: a first message has
nothing to resolve.

| Technique | Extra cost per query | Use when |
|---|---|---|
| Conversational rewrite | 1 small call | Any multi-turn chat with retrieval. Always. |
| Query rewrite | 1 small call | Queries are messy or chatty |
| Multi-query + RRF | 1 call + n× searches | Recall is the problem, latency is not |
| HyDE | 1 larger call | Short queries against long documents; measure first |

## 7. Better chunks: contextual headers and parent documents

### Contextual chunk headers

Chapter 6's chunker produces chunks like this one, from a page titled *Terminal T2*:

```
Charge it for 2 hours before first use. A full charge lasts for about 300 transactions.
```

Ask "T2 battery life" and nothing matches — "T2" is in the page title, not the chunk.
The chunk has lost its context. The fix is almost free: **prepend the document title
and section to each chunk before you index it.**

```
Terminal T2
Charge it for 2 hours before first use. A full charge lasts for about 300 transactions.
```

In Exercise 5 this one change takes that query from "not found" to rank 2.

The heavier version, **contextual retrieval**, asks a model to write one or two
sentences of context for each chunk ("This chunk is from the T2 terminal manual,
section Battery…") and prepends that. Anthropic reported in 2024 that this cut
top-20 retrieval failures by about a third with embeddings alone, about half when
combined with BM25, and about two-thirds with reranking on top. It costs one model
call per chunk at index time (cheap with prompt caching), and nothing at query time.

### Parent-document retrieval

Small chunks retrieve precisely; big chunks give the model enough to work with. You
can have both: **search small, return big.**

```python
# index time: small chunks, each pointing at its parent section
for section_id, section_text in sections.items():
    for i, chunk in enumerate(chunk_text(section_text, max_chars=300, overlap=50)):
        store.add(chunk, doc_id=f"{section_id}#{i}", metadata={"parent": section_id})

# query time: find chunks, return their parents (deduplicated, in rank order)
parents = []
for hit in store.search(query, k=20):
    parent = hit.metadata["parent"]
    if parent not in parents:
        parents.append(parent)
context = [sections[p] for p in parents[:3]]
```

Watch the budget: three parent sections can be ten times the tokens of five
chunks. Chapter 4's context budget applies.

## 8. Measuring retrieval on its own

### Why separately

Measure end-to-end answers only and a retrieval failure looks like a model failure.
You change the prompt, it doesn't help, you change the model, it doesn't help. Measure
retrieval directly and you know in seconds — **and it is free**: no model in the
loop, deterministic, fast enough to run on every change.

### The golden set

A list of `(query, ids of the documents that answer it)`. That is all.

- **Start with 30–50 queries.** You can label that in an afternoon. 15, as in
  Exercise 5, is enough to learn with and too few to trust small differences.
- **Take them from real logs** if you have any. Questions you make up are easier
  than the ones users ask.
- **Cover the failure buckets on purpose:** identifiers, paraphrases, follow-ups,
  queries whose answer is in a title. Section 2's table is a checklist.
- **Label documents, not chunk ids.** Re-chunk and every chunk id changes, and a
  golden set keyed on chunk ids silently breaks. Label by stable document or
  section ids, and map chunks back to them before scoring.
- **Add every retrieval failure you see in production.** A golden set grows from
  real mistakes.

### The metrics

One query, relevant = {a, b, c}, retrieved = `[x, a, y, b, z]`, k = 5:

| Metric | Question it answers | Here |
|---|---|---|
| **recall@k** | What share of the right documents did we find? | 2/3 = 0.667 |
| **precision@k** | What share of what we returned is right? | 2/5 = 0.40 |
| **hit@k** (hit rate) | Did we find *anything* useful? | 1 |
| **MRR** (reciprocal rank) | How high is the *first* right answer? | 1/2 = 0.50 |
| **nDCG@k** | Are the right answers near the top, all of them? | 0.498 |

nDCG gives each position a value — 1.00, 0.63, 0.50, 0.43, 0.39 for ranks 1–5 (that
is 1/log2(rank+1)) — adds up the values of the relevant positions, then divides by
the best score possible. Here: (0.63 + 0.43) / (1.00 + 0.63 + 0.50) = 0.498.

**Which one to watch:**
- **recall@k** for RAG. The model reads all k passages, so their order matters less
  than whether the right one is there. Recall@5 of 0.7 means at most ~70% of answers
  can be grounded, *whatever model you use*.
- **MRR / nDCG** when order matters: a person reads the list, or k is small (1–3)
  because context is tight.
- **precision@k** when every wrong passage costs you — tokens, or distraction (a
  wrong passage in context can pull the model toward a wrong answer).

### What Exercise 5 shows

```
retriever                   R@5      P@5      MRR   nDCG@5    Hit@5
------------------------------------------------------------------------
vector only               0.900    0.187    0.728    0.754    0.933
bm25 only                 0.600    0.120    0.600    0.600    0.600
hybrid                    0.900    0.187    0.836    0.833    0.933
hybrid + headers          1.000    0.213    0.839    0.880    1.000
```

BM25 misses every paraphrase. Vector search finds nearly everything but ranks the
identifier queries 2nd or 3rd. The hybrid keeps vector search's recall *and* puts
identifiers first, so MRR goes up. Headers fix the one query whose answer lived in
a title. The per-query table under it shows *which* query moved and why — that
table is the one you learn from.

## 9. Agentic RAG: retrieval as a tool

Everything so far retrieves on every turn and stuffs the results into the prompt.
The alternative is to give the agent a search tool and let it decide.

```python
@tool
def search_docs(query: str) -> str:
    """Search the help centre. Use short keyword queries; include exact error codes."""
    hits = hybrid.search(query, k=5)
    return "\n\n".join(f"[{h.doc_id}] {h.text}" for h in hits) or "No results."

SYSTEM = """Answer using search_docs. Cite every fact with its [doc id].
If the results do not contain the answer, say so — do not guess."""
```

| | Always retrieve | Retrieval as a tool |
|---|---|---|
| Cost | Retrieval + tokens every turn | Only when the agent searches |
| "Thanks!" | Retrieves anyway, wastes tokens | Skips it |
| Multi-hop questions | One search, fixed query | Search, read, search again with what it learned |
| Query quality | Needs a separate rewrite step | The model writes the query — a free conversational rewrite |
| Failure mode | Irrelevant context | Agent doesn't search when it should, or searches 8 times |

A common middle ground: always retrieve a small amount, *and* give the agent the
tool for more. Cap the number of searches per turn (Chapter 3's step limit).

**Check citations in code.** After the answer comes back, every `[doc id]` it cites
must be one that a search actually returned this turn. A citation to an id that was
never retrieved is a hallucination with a footnote, and it is a one-line check.

## 10. When to stop building your own

What you built is the real algorithm, in memory. Honest limits: BM25 here re-scans
candidates in Python and keeps everything in RAM — fine to roughly 100k chunks, and
the vector store hits its own limit around 50k (Chapter 6).

| Option | Keyword | Vector | Fusion | Pick it when |
|---|---|---|---|---|
| **Postgres** + full-text + `pgvector` | `tsvector` / `ts_rank` (not true BM25; extensions such as ParadeDB add BM25) | `pgvector` (HNSW) | RRF in one SQL query | You already run Postgres. Usually the right answer. |
| **Elasticsearch / OpenSearch** | BM25, the reference implementation | kNN | Built-in hybrid queries | Search is a core feature, or you already run it |
| **Qdrant / Weaviate** | Sparse vectors / BM25 | Native | Built-in hybrid | You want a purpose-built vector DB with hybrid included |
| **Hosted rerankers**: Cohere, Voyage, Jina | — | — | — | You want a cross-encoder without hosting a model |

**What to keep when you switch:** the golden set and `evaluate_retriever`. They do
not care what is behind `retriever_fn(query, k)`, so the day you move to pgvector
you run the same table and know whether it got better or worse. That is the
part of this chapter that lasts.

## 11. Common mistakes

1. **Fixing the prompt when retrieval failed.** Check whether the answer was in the context first.
2. **Vector search alone for anything with codes, IDs or names.** It blurs them.
3. **BM25 alone for anything people phrase in their own words.** It needs shared words.
4. **Adding BM25 and cosine scores.** Different scales; the bigger numbers win. Fuse ranks.
5. **Fetching 5 from each side and fusing.** Fusion can only promote what was fetched. Fetch ~50.
6. **Reranking the whole corpus.** Cross-encoders are per-pair model calls. Rerank ~50, keep ~5.
7. **A reranker that raises on a bad reply.** It must fail open, and count when it does.
8. **Never looking at the fallback count.** A reranker that always falls back looks like one that works.
9. **Multi-query expansion that drops the original query.** One bad rewrite and you lost the user's words.
10. **Embedding follow-up questions as-is.** "What about the second one?" retrieves nothing useful.
11. **Chunks that don't say what they are about.** Prepend the title and section.
12. **No golden set.** Without one, every change to retrieval is a guess.
13. **A golden set keyed on chunk ids.** It silently breaks the next time you re-chunk.
14. **Judging retrieval by eye on three queries.** Run the numbers; look at the per-query misses.
15. **Unchecked citations.** Verify every cited id was actually retrieved.

## 12. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_bm25.py` | `BM25Index` — smoothed IDF, tf saturation, length normalisation |
| 2 | `exercise_2_metrics.py` | `recall_at_k`, `precision_at_k`, `hit_at_k`, `reciprocal_rank`, `ndcg_at_k`, `evaluate_retriever` |
| 3 | `exercise_3_hybrid.py` | `reciprocal_rank_fusion`, `HybridRetriever` |
| 4 | `exercise_4_rerank_and_rewrite.py` | `LLMReranker` (fails open), `expand_query`, `multi_query_retrieve`, `rewrite_followup` |
| 5 | `exercise_5_measure_it.py` | **Integration:** four retrievers, one golden set, one table — plus an optional LLM reranker |

```bash
pytest chapters/ch06b_retrieval/tests -q
```

## 13. Check yourself

1. Give two kinds of query where vector search fails and two where BM25 fails. Why, in each case?
2. What do IDF, k1 and b each do in BM25? What happens at k1 = 0 and at b = 0?
3. Why does the original IDF formula go negative, and why is that a bug?
4. In the worked example, d3 says "card" three times. Why does d2 still win?
5. Why can't you add a BM25 score to a cosine similarity? Why doesn't min-max normalising fully fix it?
6. Write the RRF formula. What does k = 60 do that k = 0 doesn't?
7. Why must you fetch more candidates than you return before fusing or reranking?
8. What can a cross-encoder see that a bi-encoder can't? Why can't you run it over the whole corpus?
9. Why does the reranker fail open while Chapter 11's judge fails closed?
10. Rewrite "what about the second one?" given a conversation of your choice. When can you skip the rewrite call?
11. A chunk says "Charge it for 2 hours." What goes wrong, and what is the cheap fix?
12. Recall@5 is 0.6. What does that tell you about the best possible answer accuracy?
13. When would you watch MRR instead of recall@k?
14. Why should a golden set label documents rather than chunk ids?
15. Name one advantage and one risk of making retrieval a tool the agent calls.

---

**Next:** Chapter 7 — the agent stops reacting and starts planning: decomposition,
plan-execute, and self-critique.
