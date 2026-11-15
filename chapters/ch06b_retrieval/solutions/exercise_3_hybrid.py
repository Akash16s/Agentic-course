"""SOLUTION — Chapter 6b, Exercise 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from agentlib.memory.vector import VectorStore

from .exercise_1_bm25 import BM25Index


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
) -> list[tuple[str, float]]:
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
