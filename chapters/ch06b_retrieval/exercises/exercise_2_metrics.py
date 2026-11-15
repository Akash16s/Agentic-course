"""EXERCISE 2 — Measuring retrieval on its own.

    pytest chapters/ch06b_retrieval/tests -q -k metrics

Every function here takes `retrieved` (doc ids, best first, as your retriever
returned them) and `relevant` (the ids a human said answer the query). Three rules
apply to ALL of them, so write two small helpers first:

  1. DEDUPLICATE `retrieved` before anything else, keeping the first occurrence.
     A retriever that returns the same document twice must not get credit twice.
  2. Then take the first k. If there are fewer than k results, use what there is.
  3. k < 1 -> ValueError. (`reciprocal_rank` allows k=None, meaning "no cut-off".)

And one convention: an EMPTY `relevant` set gives 0.0. Every metric is undefined
for a query with no right answer; returning 0.0 instead of raising means one bad
golden row cannot crash a whole evaluation. `evaluate_retriever` skips such rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class GoldenQuery:
    """One labelled query: the question, and the ids of the documents that answer it.

    `relevant` is converted to a frozenset, so passing a list or set is fine.
    """

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
    """Averages over a golden set. `n` counts the queries that were scored."""

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


# ------------------------------------------------------------------ metrics


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Of the documents that answer the query, what fraction made the top k?

        recall@k = |relevant ∩ top_k| / |relevant|

    The metric to watch for RAG. A passage that is not retrieved cannot be used,
    however good the model is — recall is the ceiling on answer quality.
    """
    # TODO: implement
    raise NotImplementedError


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Of the top k, what fraction is relevant?

        precision@k = |relevant ∩ top_k| / k

    Divide by k, NOT by len(retrieved). This is the standard definition: a retriever
    that returns 2 results when asked for 5 has 3 empty slots, and an empty slot is
    not a relevant one. (Dividing by len(retrieved) would reward returning less.)
    """
    # TODO: implement
    raise NotImplementedError


def hit_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """1.0 if ANY relevant document is in the top k, else 0.0.

    Averaged over queries this is the "hit rate": the share of questions for which
    the model got at least one useful passage. Crude, and very easy to explain to
    the rest of your team.
    """
    # TODO: implement
    raise NotImplementedError


def reciprocal_rank(
    retrieved: Sequence[str], relevant: Iterable[str], k: int | None = None
) -> float:
    """1 / (rank of the FIRST relevant document), ranks counted from 1.

    Spec:
      * first relevant at rank 1 -> 1.0, rank 2 -> 0.5, rank 4 -> 0.25
      * nothing relevant (within the top k, if k is given) -> 0.0
      * k=None means look at the whole (deduplicated) list

    It only cares about the first hit — which matches how people (and models)
    actually read: the top result gets most of the attention.
    """
    # TODO: implement
    raise NotImplementedError


def mean_reciprocal_rank(
    runs: Iterable[tuple[Sequence[str], Iterable[str]]], k: int | None = None
) -> float:
    """The mean of `reciprocal_rank` over (retrieved, relevant) pairs. No pairs -> 0.0."""
    # TODO: implement
    raise NotImplementedError


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Normalised Discounted Cumulative Gain, with binary relevance (1 or 0).

        DCG@k  = sum over positions i = 1..k of  rel_i / log2(i + 1)
        IDCG@k = DCG@k of the PERFECT ranking: all relevant docs first, i.e.
                 sum over i = 1..min(|relevant|, k) of 1 / log2(i + 1)
        nDCG@k = DCG@k / IDCG@k                      always in [0, 1]

    Position 1 is worth 1.0, position 2 is worth 0.63, position 3 is worth 0.5,
    position 10 is worth 0.29. So unlike recall it rewards putting the right
    documents HIGHER, and unlike MRR it counts every relevant document, not just
    the first.

    Note the min() in IDCG: with 3 relevant docs and k=2 a perfect top-2 must score
    1.0, so the ideal ranking only has room for 2 of them.
    """
    # TODO: implement
    raise NotImplementedError


# --------------------------------------------------------------- the harness


def evaluate_retriever(
    retriever_fn: Callable[[str, int], Sequence[str]],
    golden: Iterable[GoldenQuery | tuple[str, Iterable[str]]],
    *,
    k: int = 5,
) -> RetrievalReport:
    """Run every golden query through `retriever_fn(query, k)` and average.

    Spec:
      * each golden item is a GoldenQuery or a (query, relevant) pair — turn pairs
        into GoldenQuery
      * an item with no relevant ids is SKIPPED: not scored, not averaged, counted
        in `skipped`. Averaging in a 0.0 would punish the retriever for a hole in
        your labels
      * call `retriever_fn(query, k)` exactly once per scored item; deduplicate what
        it returns and keep the first k — that is the `retrieved` you store
      * fill one QueryScore per scored item, in golden-set order, using the
        functions above with this k
      * averages are plain means over the scored items; with none scored, every
        average is 0.0 and n is 0

    The point of this function is that it measures retrieval WITHOUT a model in
    the loop: it is free, deterministic and fast, so you can run it on every change.
    """
    # TODO: implement
    raise NotImplementedError
