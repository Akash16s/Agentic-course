"""SOLUTION — Chapter 6b, Exercise 2."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence


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
