"""Retrieval quality — keyword search, fusion, reranking and measuring it all.

Promoted from Chapter 6b.

Chapter 6 gave you a vector store. This module is what you put AROUND it once you
notice that "top 5 by cosine" is not the same thing as "the 5 passages that answer
the question":

  * `BM25Index`              keyword search with the scoring every search engine uses
  * metrics                  recall@k, precision@k, MRR, nDCG, hit rate — so you can
                             measure retrieval on its own, before generation hides it
  * `reciprocal_rank_fusion` merge several rankings without comparing their scores
  * `HybridRetriever`        vector + BM25, fused
  * `LLMReranker`            a model re-orders a wide candidate list; fails open
  * `expand_query`,          query transformation: several phrasings, and turning a
    `rewrite_followup`       follow-up ("what about the second one?") into a
                             question that can be searched on its own

Everything here is pure Python and offline except the two functions that take a
client, and those accept anything with a `chat(messages, **kwargs)` method — so
`agentlib.testing.FakeLLMClient` works in tests.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from agentlib.embeddings import tokenise
from agentlib.memory.vector import VectorStore

#: (doc_id, score) pairs, best first.
Ranking = list[tuple[str, float]]


# ===================================================================== BM25


class BM25Index:
    """Okapi BM25 over an in-memory inverted index.

        score(D, Q) = sum over terms t in Q of
                      IDF(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |D| / avgdl))

        IDF(t)      = ln(1 + (N - n + 0.5) / (n + 0.5))

    tf     how often t appears in D
    |D|    D's length in tokens; avgdl the average length over the index
    N      documents in the index; n documents containing t

    k1 (default 1.5) controls tf SATURATION: the 1st mention of a term matters a lot,
    the 10th barely at all. b (default 0.75) controls LENGTH NORMALISATION: a long
    document mentions everything a few times by accident, so its tf counts for less.

    The "1 +" inside the log is the smoothed IDF used by Lucene/Elasticsearch. The
    original formula goes NEGATIVE for a term in more than half the documents, which
    means matching a common word would make a document rank lower than not matching
    it at all.

    >>> index = BM25Index()
    >>> index.add("a", "error E4012 means the card was declined")
    >>> index.add("b", "how to handle payment errors gracefully")
    >>> index.search("E4012")[0][0]
    'a'
    """

    def __init__(
        self,
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Callable[[str], list[str]] = tokenise,
    ) -> None:
        if k1 < 0:
            raise ValueError(f"k1 must be >= 0, got {k1}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b must be in [0, 1], got {b}")
        self.k1 = k1
        self.b = b
        self.tokenizer = tokenizer
        self._texts: dict[str, str] = {}
        self._tf: dict[str, dict[str, int]] = {}      # doc_id -> term -> count
        self._lengths: dict[str, int] = {}             # doc_id -> token count
        self._df: dict[str, int] = {}                  # term -> docs containing it
        self._total_length = 0

    # ------------------------------------------------------------- writing

    def add(self, doc_id: str, text: str) -> None:
        """Index one document. Re-adding an existing id replaces it."""
        if doc_id in self._texts:
            self.remove(doc_id)
        tokens = self.tokenizer(text)
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        self._texts[doc_id] = text
        self._tf[doc_id] = counts
        self._lengths[doc_id] = len(tokens)
        self._total_length += len(tokens)
        for term in counts:
            self._df[term] = self._df.get(term, 0) + 1

    def add_many(self, items: Iterable[tuple[str, str]]) -> None:
        for doc_id, text in items:
            self.add(doc_id, text)

    def remove(self, doc_id: str) -> bool:
        if doc_id not in self._texts:
            return False
        for term in self._tf[doc_id]:
            self._df[term] -= 1
            if self._df[term] == 0:
                del self._df[term]
        self._total_length -= self._lengths[doc_id]
        del self._texts[doc_id], self._tf[doc_id], self._lengths[doc_id]
        return True

    # ------------------------------------------------------------- reading

    def __len__(self) -> int:
        return len(self._texts)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self._texts

    def get(self, doc_id: str) -> str | None:
        return self._texts.get(doc_id)

    @property
    def avgdl(self) -> float:
        """Average document length in tokens. 0.0 for an empty index."""
        return self._total_length / len(self._texts) if self._texts else 0.0

    def idf(self, term: str) -> float:
        """Smoothed IDF. Never negative; 0.0 for a term no document contains."""
        n = self._df.get(term, 0)
        if n == 0:
            return 0.0
        N = len(self._texts)
        return math.log(1.0 + (N - n + 0.5) / (n + 0.5))

    def score(self, query: str, doc_id: str) -> float:
        """BM25 score of one document. Duplicate query terms count once."""
        counts = self._tf.get(doc_id)
        if counts is None:
            return 0.0
        avgdl = self.avgdl or 1.0  # every doc empty: avoid dividing by zero
        length_ratio = self._lengths[doc_id] / avgdl
        total = 0.0
        for term in set(self.tokenizer(query)):
            tf = counts.get(term, 0)
            if tf == 0:
                continue
            norm = tf + self.k1 * (1.0 - self.b + self.b * length_ratio)
            total += self.idf(term) * tf * (self.k1 + 1.0) / norm
        return total

    def search(self, query: str, k: int = 10) -> Ranking:
        """Top-k (doc_id, score), best first.

        Only documents matching at least one query term are returned — unlike vector
        search, BM25 is allowed to say "nothing matched". Ties keep insertion order.
        """
        if k <= 0 or not self._texts:
            return []
        terms = set(self.tokenizer(query))
        # only score documents that contain at least one query term
        candidates = [d for d in self._texts if any(t in self._tf[d] for t in terms)]
        scored = [(d, self.score(query, d)) for d in candidates]
        scored = [(d, s) for d, s in scored if s > 0.0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]


# ================================================================== metrics


@dataclass(frozen=True)
class GoldenQuery:
    """One labelled query: the question, and the ids of the documents that answer it."""

    query: str
    relevant: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "relevant", frozenset(self.relevant))


@dataclass
class QueryScore:
    """Every metric for one query, so you can find the ones that failed."""

    query: str
    retrieved: list[str]
    relevant: frozenset[str]
    recall: float
    precision: float
    reciprocal_rank: float
    ndcg: float
    hit: float


@dataclass
class RetrievalReport:
    """Averages over a golden set."""

    k: int
    n: int
    recall: float
    precision: float
    mrr: float
    ndcg: float
    hit_rate: float
    skipped: int = 0
    per_query: list[QueryScore] = field(default_factory=list)

    @property
    def misses(self) -> list[QueryScore]:
        """Queries where nothing relevant made the top k. Read these first."""
        return [q for q in self.per_query if q.hit == 0.0]

    def row(self, name: str) -> str:
        return (f"{name:<22} {self.recall:>8.3f} {self.precision:>8.3f} "
                f"{self.mrr:>8.3f} {self.ndcg:>8.3f} {self.hit_rate:>8.3f}")

    @staticmethod
    def header(k: int) -> str:
        return (f"{'retriever':<22} {f'R@{k}':>8} {f'P@{k}':>8} {'MRR':>8} "
                f"{f'nDCG@{k}':>8} {f'Hit@{k}':>8}")


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    return [x for x in items if not (x in seen or seen.add(x))]


def _top(retrieved: Sequence[str], k: int) -> list[str]:
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    return _dedupe(retrieved)[:k]


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of the relevant documents that appear in the top k."""
    relevant = set(relevant)
    top = _top(retrieved, k)
    if not relevant:
        return 0.0
    return sum(1 for d in top if d in relevant) / len(relevant)


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of the top k that is relevant. Divides by k, not by len(retrieved)."""
    relevant = set(relevant)
    top = _top(retrieved, k)
    if not relevant:
        return 0.0
    return sum(1 for d in top if d in relevant) / k


def hit_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """1.0 if anything relevant is in the top k, else 0.0."""
    relevant = set(relevant)
    return 1.0 if any(d in relevant for d in _top(retrieved, k)) else 0.0


def reciprocal_rank(
    retrieved: Sequence[str], relevant: Iterable[str], k: int | None = None
) -> float:
    """1 / rank of the first relevant document; 0.0 if none (within k, if given)."""
    relevant = set(relevant)
    top = _dedupe(retrieved) if k is None else _top(retrieved, k)
    for rank, doc_id in enumerate(top, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    runs: Iterable[tuple[Sequence[str], Iterable[str]]], k: int | None = None
) -> float:
    """Mean of `reciprocal_rank` over (retrieved, relevant) pairs. 0.0 for none."""
    values = [reciprocal_rank(r, rel, k) for r, rel in runs]
    return sum(values) / len(values) if values else 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Normalised discounted cumulative gain, binary relevance.

        DCG  = sum over positions i = 1..k of rel_i / log2(i + 1)
        IDCG = the DCG of a perfect ranking (all relevant docs first)
        nDCG = DCG / IDCG, in [0, 1]
    """
    relevant = set(relevant)
    top = _top(retrieved, k)
    if not relevant:
        return 0.0
    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(top, start=1) if d in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal


def evaluate_retriever(
    retriever_fn: Callable[[str, int], Sequence[str]],
    golden: Iterable[GoldenQuery | tuple[str, Iterable[str]]],
    *,
    k: int = 5,
) -> RetrievalReport:
    """Run every golden query through `retriever_fn(query, k)` and average the metrics.

    Queries with no relevant documents are skipped (and counted in `skipped`): every
    metric here is undefined for them, and averaging in a 0.0 would punish the
    retriever for a hole in your labels.
    """
    scores: list[QueryScore] = []
    skipped = 0
    for item in golden:
        g = item if isinstance(item, GoldenQuery) else GoldenQuery(item[0], item[1])
        if not g.relevant:
            skipped += 1
            continue
        retrieved = _dedupe(retriever_fn(g.query, k))[:k]
        scores.append(QueryScore(
            query=g.query,
            retrieved=retrieved,
            relevant=g.relevant,
            recall=recall_at_k(retrieved, g.relevant, k),
            precision=precision_at_k(retrieved, g.relevant, k),
            reciprocal_rank=reciprocal_rank(retrieved, g.relevant, k),
            ndcg=ndcg_at_k(retrieved, g.relevant, k),
            hit=hit_at_k(retrieved, g.relevant, k),
        ))

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    return RetrievalReport(
        k=k,
        n=len(scores),
        recall=mean([s.recall for s in scores]),
        precision=mean([s.precision for s in scores]),
        mrr=mean([s.reciprocal_rank for s in scores]),
        ndcg=mean([s.ndcg for s in scores]),
        hit_rate=mean([s.hit for s in scores]),
        skipped=skipped,
        per_query=scores,
    )


# =================================================================== fusion


def _doc_id(item: Any) -> str:
    """A ranking item is a bare id, an (id, score) pair, or anything with `.doc_id`."""
    if isinstance(item, str):
        return item
    if isinstance(item, (tuple, list)):
        return item[0]
    return item.doc_id


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Any]],
    *,
    k: int = 60,
    weights: Sequence[float] | None = None,
) -> Ranking:
    """Merge rankings by position, ignoring their scores.

        fused(d) = sum over rankings i of  weight_i / (k + rank_i(d))     (rank from 1)

    WHY RANKS, NOT SCORES: BM25 scores are unbounded (3.2, 17.9, ...), cosine is in
    [-1, 1], a reranker returns 0-10. Adding them lets whichever has the biggest
    numbers win. Ranks are on the same scale by construction.

    WHY k=60: it flattens the curve so that rank 1 vs rank 2 is not a big deal, but
    being in the list at all is. From Cormack et al. (2009); it is still the default
    in Elasticsearch, OpenSearch and most vector databases.
    """
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError(f"{len(weights)} weights for {len(rankings)} rankings")

    fused: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        seen: set[str] = set()
        rank = 0
        for item in ranking:
            doc_id = _doc_id(item)
            if doc_id in seen:
                continue  # a duplicate within one list gets no extra credit
            seen.add(doc_id)
            rank += 1
            fused[doc_id] = fused.get(doc_id, 0.0) + weight / (k + rank)
    ordered = sorted(fused.items(), key=lambda pair: pair[1], reverse=True)
    return ordered


@dataclass
class HybridHit:
    """One fused result, with where it ranked in each list (None = not in that list).

    The two ranks are there for debugging: "why did this come back?" is answered by
    looking at which retriever found it.
    """

    doc_id: str
    score: float
    text: str = ""
    vector_rank: int | None = None
    bm25_rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """Vector search and BM25 over the same documents, fused with RRF.

    >>> hybrid = HybridRetriever(VectorStore(HashingEmbedder()), BM25Index())
    >>> hybrid.add("kb-1", "Error E4012: card declined by issuer")
    >>> hybrid.search("E4012", k=1)[0].doc_id
    'kb-1'
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        *,
        rrf_k: int = 60,
        weights: tuple[float, float] = (1.0, 1.0),
    ) -> None:
        self.vector_store = vector_store
        self.bm25 = bm25_index
        self.rrf_k = rrf_k
        self.weights = weights

    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add to BOTH indexes. One method so they cannot drift apart."""
        self.vector_store.add(text, doc_id=doc_id, metadata=metadata)
        self.bm25.add(doc_id, text)

    def add_many(
        self,
        items: Iterable[tuple[str, str]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        items = list(items)
        if not items:
            return
        ids = [doc_id for doc_id, _ in items]
        texts = [text for _, text in items]
        self.vector_store.add_many(texts, ids=ids, metadatas=metadatas)
        self.bm25.add_many(items)

    def search(self, query: str, k: int = 5, *, candidates: int = 50) -> list[HybridHit]:
        """Retrieve `candidates` from each index, fuse, return the top k."""
        if k <= 0:
            return []
        candidates = max(candidates, k)
        vector_ids = [r.document.id for r in self.vector_store.search(query, k=candidates)]
        bm25_ids = [doc_id for doc_id, _ in self.bm25.search(query, k=candidates)]
        fused = reciprocal_rank_fusion(
            [vector_ids, bm25_ids], k=self.rrf_k, weights=list(self.weights)
        )
        vector_rank = {d: i for i, d in enumerate(vector_ids, start=1)}
        bm25_rank = {d: i for i, d in enumerate(bm25_ids, start=1)}

        hits: list[HybridHit] = []
        for doc_id, score in fused[:k]:
            document = self.vector_store.get(doc_id)
            text = document.text if document else (self.bm25.get(doc_id) or "")
            hits.append(HybridHit(
                doc_id=doc_id,
                score=score,
                text=text,
                vector_rank=vector_rank.get(doc_id),
                bm25_rank=bm25_rank.get(doc_id),
                metadata=dict(document.metadata) if document else {},
            ))
        return hits

    def search_ids(self, query: str, k: int = 5) -> list[str]:
        """Just the ids — the shape `evaluate_retriever` wants."""
        return [hit.doc_id for hit in self.search(query, k)]


# ================================================================ reranking


_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def parse_json(raw: str | None) -> Any | None:
    """The first JSON value found in a model reply. None on failure; never raises.

    Tries, in order: the whole reply, the inside of a ``` fence, the widest {...}
    span, the widest [...] span.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    candidates = [text, *(block.strip() for block in _FENCE.findall(text))]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            candidates.append(text[start: end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


RERANK_PROMPT = """\
You are ranking search results. Score how well each passage answers the query.

QUERY: {query}

PASSAGES:
{passages}

Score every passage from 0 (irrelevant) to 10 (directly answers the query).
Judge only relevance to the query, not writing quality.

Return ONLY JSON, one entry per passage number:
{{"scores": {{"0": <0-10>, "1": <0-10>, ...}}}}"""


@dataclass
class RerankResult:
    """One reranked candidate. `score` is None when the model gave it no score."""

    doc_id: str
    text: str
    score: float | None
    original_rank: int


def _chat_text(client: Any, prompt: str, *, model: str | None, max_tokens: int) -> str:
    kwargs: dict[str, Any] = {"temperature": 0.0, "max_tokens": max_tokens}
    if model is not None:
        kwargs["model"] = model
    return client.chat([{"role": "user", "content": prompt}], **kwargs).text


class LLMReranker:
    """Ask a model to score (query, passage) pairs, then sort by that score.

    This is a cross-encoder built out of a chat model: the model reads the query and
    each passage TOGETHER, which is what makes it more accurate than comparing two
    independently computed embeddings — and what makes it far too slow to run over
    your whole corpus. So: retrieve wide (~50), rerank narrow (~5).

    FAILS OPEN. Reranking is an improvement on an order you already have. If the
    model returns garbage or the call errors, you return the original order and count
    a fallback — you do not fail the user's request over an optimisation.
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str | None = None,
        max_chars: int = 500,
        max_tokens: int = 512,
    ) -> None:
        self.client = client
        self.model = model
        self.max_chars = max_chars
        self.max_tokens = max_tokens
        self.fallbacks = 0

    def prompt(self, query: str, candidates: Sequence[tuple[str, str]]) -> str:
        passages = "\n\n".join(
            f"[{i}] {' '.join(text.split())[: self.max_chars]}"
            for i, (_, text) in enumerate(candidates)
        )
        return RERANK_PROMPT.format(query=query, passages=passages)

    def parse(self, raw: str | None, n: int) -> dict[int, float] | None:
        """{index: score} for the valid entries, or None if nothing usable came back."""
        obj = parse_json(raw)
        if not isinstance(obj, dict):
            return None
        scores = obj.get("scores", obj)
        if not isinstance(scores, dict):
            return None
        parsed: dict[int, float] = {}
        for key, value in scores.items():
            try:
                index = int(str(key).strip().strip("[]"))
                if isinstance(value, bool):
                    raise TypeError("a bool is not a score")
                score = float(value)
            except (TypeError, ValueError):
                continue
            if 0 <= index < n and math.isfinite(score):
                parsed[index] = min(10.0, max(0.0, score))
        return parsed or None

    def rerank(
        self,
        query: str,
        candidates: Sequence[tuple[str, str]],
        top_n: int | None = 5,
    ) -> list[RerankResult]:
        candidates = list(candidates)
        limit = len(candidates) if top_n is None else max(0, top_n)
        if len(candidates) <= 1:
            return [RerankResult(d, t, None, i) for i, (d, t) in enumerate(candidates)][:limit]

        try:
            raw = _chat_text(self.client, self.prompt(query, candidates),
                             model=self.model, max_tokens=self.max_tokens)
            scores = self.parse(raw, len(candidates))
        except Exception:  # noqa: BLE001 - fail open on anything
            scores = None

        if scores is None:
            self.fallbacks += 1
            scores = {}

        results = [
            RerankResult(doc_id, text, scores.get(i), i)
            for i, (doc_id, text) in enumerate(candidates)
        ]
        # scored first, by score; unscored after, in their original order
        results.sort(key=lambda r: (r.score is None, -(r.score or 0.0), r.original_rank))
        return results[:limit]


# ======================================================= query transformation


EXPAND_PROMPT = """\
Write {n} different search queries that would find documents answering the question
below. Use different wording and synonyms; keep each one short. Do not answer it.

QUESTION: {query}

Return ONLY a JSON array of {n} strings."""


def _normalise_query(text: str) -> str:
    return " ".join(text.lower().split())


def expand_query(client: Any, query: str, n: int = 3, *, model: str | None = None) -> list[str]:
    """[query] + up to n alternative phrasings. Always starts with the original.

    Fails safe: garbage, an empty reply or an exception gives back [query].
    """
    if n <= 0:
        return [query]
    try:
        raw = _chat_text(client, EXPAND_PROMPT.format(n=n, query=query),
                         model=model, max_tokens=300)
    except Exception:  # noqa: BLE001
        return [query]

    parsed = parse_json(raw)
    if isinstance(parsed, dict):
        parsed = parsed.get("queries")
    if not isinstance(parsed, list):
        return [query]

    out = [query]
    seen = {_normalise_query(query)}
    for item in parsed:
        if not isinstance(item, str):
            continue
        cleaned = " ".join(item.split())
        key = _normalise_query(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) == n + 1:
            break
    return out


def multi_query_retrieve(
    queries: Sequence[str],
    retrieve_fn: Callable[[str, int], Sequence[Any]],
    k: int = 5,
    *,
    per_query: int | None = None,
    rrf_k: int = 60,
) -> list[str]:
    """Run every query, fuse the rankings with RRF, return the top k ids."""
    if k <= 0 or not queries:
        return []
    per_query = per_query or max(k * 2, 10)
    rankings = [list(retrieve_fn(q, per_query)) for q in queries]
    return [doc_id for doc_id, _ in reciprocal_rank_fusion(rankings, k=rrf_k)[:k]]


REWRITE_PROMPT = """\
Rewrite the user's latest message as a single standalone search query. Resolve every
pronoun and reference ("it", "that one", "the second one") using the conversation.
Do not answer it. If it is already standalone, return it unchanged.

CONVERSATION:
{history}

LATEST MESSAGE: {question}

Return ONLY the rewritten query, on one line."""

_LABEL = re.compile(r"^(standalone (search )?(query|question)|rewritten( query)?|query)\s*:\s*",
                    re.IGNORECASE)


def rewrite_followup(
    client: Any,
    history: Sequence[dict[str, Any]],
    question: str,
    *,
    max_turns: int = 6,
    max_chars: int = 500,
    model: str | None = None,
) -> str:
    """Turn a follow-up into a query that makes sense with no conversation around it.

    "what about the second one?" embeds as nothing in particular. After rewriting it
    is "pricing of the Pro plan", which retrieves. Fails safe to the original question.
    """
    turns = [
        m for m in history
        if m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str) and m["content"].strip()
    ]
    turns = turns[-max_turns:] if max_turns > 0 else []
    if not turns:
        return question

    transcript = "\n".join(f"{m['role']}: {m['content'].strip()}" for m in turns)
    try:
        raw = _chat_text(client, REWRITE_PROMPT.format(history=transcript, question=question),
                         model=model, max_tokens=200)
    except Exception:  # noqa: BLE001
        return question

    lines = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not lines:
        return question
    text = _LABEL.sub("", lines[0]).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'`":
        text = text[1:-1].strip()
    if not text or len(text) > max_chars:
        return question
    return text
