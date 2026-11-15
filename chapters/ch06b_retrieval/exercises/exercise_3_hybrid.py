"""EXERCISE 3 — Hybrid search: vectors + BM25, fused by rank.

    pytest chapters/ch06b_retrieval/tests -q -k hybrid
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from agentlib.memory.vector import VectorStore

from .exercise_1_bm25 import BM25Index


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Any]],
    *,
    k: int = 60,
    weights: Sequence[float] | None = None,
) -> list[tuple[str, float]]:
    """Merge several rankings using only the POSITIONS of the documents.

        fused(d) = sum over rankings i that contain d of   weight_i / (k + rank_i(d))

    with rank counted from 1 and every weight 1.0 by default.

    Spec:
      * each ranking is a list, best first. An item may be
            a bare doc id                    "kb-02"
            an (id, score) pair              ("kb-02", 17.3)   <- BM25Index.search
            anything with a .doc_id          (HybridHit, RerankResult, ...)
        and in every case the score is IGNORED. That is the whole point.
      * a doc that appears twice in ONE ranking only counts at its first position
        (and does not use up a rank for the second copy)
      * k < 0 -> ValueError; len(weights) != len(rankings) -> ValueError
      * return [(doc_id, fused_score)], highest first. Ties keep the order in which
        the documents were first seen, scanning ranking 0 then ranking 1 and so on
        (insert into a dict as you go, then use a stable sort)
      * no rankings, or only empty ones -> []

    WHY RANKS AND NOT SCORES: BM25 scores are unbounded (0.7, 4.2, 31.0 ...),
    cosine similarity sits in [-1, 1], an LLM reranker says 0-10. Add them and the
    retriever with the biggest numbers wins regardless of quality. Normalising each
    list to [0, 1] helps less than you would think: one outlier squashes everything
    else to near zero. Ranks are on the same scale by construction.

    WHY k = 60: with k=60, rank 1 is worth 1/61 = 0.0164 and rank 10 is worth
    1/70 = 0.0143 — close. Being found by BOTH retrievers beats being first in one.
    With k=0, rank 1 is worth 1.0 and rank 10 is worth 0.1, so one retriever's top
    pick steamrolls everything. 60 comes from the original paper (Cormack et al.,
    2009) and is still the default in Elasticsearch, OpenSearch and most vector DBs.
    """
    # TODO: implement
    raise NotImplementedError


@dataclass
class HybridHit:
    """One fused result, and where it ranked in each list (None = not in that list).

    The two ranks are for debugging. "Why did this come back?" is answered by looking
    at which retriever found it.
    """

    doc_id: str
    score: float
    text: str = ""
    vector_rank: int | None = None
    bm25_rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """Vector search and BM25 over the same documents, fused with RRF.

    __init__(self, vector_store, bm25_index, *, rrf_k=60, weights=(1.0, 1.0))
      Store them as self.vector_store, self.bm25, self.rrf_k, self.weights.
      `weights` is (vector weight, bm25 weight).

    The VectorStore is Chapter 6's, from agentlib. The BM25Index is yours, from
    Exercise 1.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        *,
        rrf_k: int = 60,
        weights: tuple[float, float] = (1.0, 1.0),
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add to BOTH indexes under the same id.

        One method that writes both, so the two indexes cannot drift apart. An id
        in one index but not the other is the classic hybrid-search bug: the
        document is findable by some queries and silently missing for others.
        """
        # TODO: implement
        raise NotImplementedError

    def add_many(
        self,
        items: Iterable[tuple[str, str]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add several (doc_id, text) pairs.

        Use ONE `vector_store.add_many(texts, ids=..., metadatas=...)` call, not a
        loop over `add` — with a real embedding API that is one request instead of
        hundreds. An empty input does nothing.
        """
        # TODO: implement
        raise NotImplementedError

    def search(self, query: str, k: int = 5, *, candidates: int = 50) -> list[HybridHit]:
        """Retrieve wide from each index, fuse, return the top k.

        Spec:
          * k <= 0 -> []
          * candidates = max(candidates, k)  (asking each side for fewer than k
            makes no sense)
          * vector side: `self.vector_store.search(query, k=candidates)`, take
            `result.document.id`
          * BM25 side:   `self.bm25.search(query, k=candidates)`, take the ids
          * fuse [vector_ids, bm25_ids] with `reciprocal_rank_fusion`, using
            self.rrf_k and self.weights
          * build a HybridHit for each of the top k: the fused score, the text and
            a COPY of the metadata from the vector store (fall back to the BM25
            text if the vector store does not have it), and the 1-based rank the
            document had in each list, or None if it was not in that list

        Why `candidates` matters: fusion can only promote documents that at least one
        side returned. If BM25 found the right document at rank 30 but you only asked
        each side for 10, fusion never sees it.
        """
        # TODO: implement
        raise NotImplementedError

    def search_ids(self, query: str, k: int = 5) -> list[str]:
        """Just the ids of `search(query, k)` — the shape `evaluate_retriever` wants."""
        # TODO: implement
        raise NotImplementedError
