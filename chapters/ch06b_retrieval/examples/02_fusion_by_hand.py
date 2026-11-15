"""Why you fuse RANKS, not scores — Reciprocal Rank Fusion step by step. Free, offline.

    python chapters/ch06b_retrieval/examples/02_fusion_by_hand.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.retrieval import reciprocal_rank_fusion

# What two retrievers returned for one query. Real-looking numbers: BM25 scores are
# unbounded, cosine similarities from an embedding model bunch up around 0.3-0.9.
BM25 = [("kb-02", 11.84), ("kb-01", 4.10), ("kb-03", 3.95), ("kb-05", 2.71)]
VECTOR = [("kb-06", 0.83), ("kb-01", 0.81), ("kb-05", 0.79), ("kb-02", 0.77)]

print("=" * 72)
print("THE TWO LISTS")
print("=" * 72)
print(f"  {'rank':<6}{'BM25':<22}{'vector'}")
for rank, ((b_id, b_s), (v_id, v_s)) in enumerate(zip(BM25, VECTOR), start=1):
    print(f"  {rank:<6}{b_id} {b_s:>6.2f}          {v_id} {v_s:.2f}")

print("\n" + "=" * 72)
print("1. NAIVE: ADD THE SCORES")
print("=" * 72)
naive: dict[str, float] = {}
for doc_id, score in BM25 + VECTOR:
    naive[doc_id] = naive.get(doc_id, 0.0) + score
for doc_id, score in sorted(naive.items(), key=lambda kv: -kv[1]):
    print(f"  {doc_id}  {score:6.2f}")
print("""
  BM25's numbers are ~10x bigger, so the vector list barely matters: the result
  is just BM25's order with noise. Swap in a retriever that scores 0-1000 and it
  would steamroll both. Adding scores from different systems is adding metres to
  kilograms.""")

print("=" * 72)
print("2. LESS NAIVE: MIN-MAX NORMALISE EACH LIST TO [0, 1], THEN ADD")
print("=" * 72)


def minmax(ranking):
    scores = [s for _, s in ranking]
    low, high = min(scores), max(scores)
    return {d: (s - low) / (high - low) if high > low else 1.0 for d, s in ranking}


normalised: dict[str, float] = {}
for part in (minmax(BM25), minmax(VECTOR)):
    for doc_id, score in part.items():
        normalised[doc_id] = normalised.get(doc_id, 0.0) + score
for doc_id, score in sorted(normalised.items(), key=lambda kv: -kv[1]):
    print(f"  {doc_id}  {score:5.2f}")
print("""
  Better, but fragile. In the vector list 0.83 vs 0.77 is a tiny gap — those four
  documents are about equally similar — yet normalising stretches it to 1.0 vs 0.0.
  And BM25's one big score (11.84) squashes everything else in its list to about 0.15
  or less. A normalised score depends on whatever else happened to be in the list.""")

print("=" * 72)
print("3. RECIPROCAL RANK FUSION: IGNORE SCORES, USE POSITIONS")
print("=" * 72)
K = 60
print(f"  fused(d) = sum over lists of 1 / (k + rank),  k = {K}\n")
bm25_rank = {d: i for i, (d, _) in enumerate(BM25, start=1)}
vector_rank = {d: i for i, (d, _) in enumerate(VECTOR, start=1)}
print(f"  {'doc':<7}{'bm25 rank':>10}{'vector rank':>13}   calculation")
for doc_id, score in reciprocal_rank_fusion([BM25, VECTOR], k=K):
    parts = []
    for ranks in (bm25_rank, vector_rank):
        if doc_id in ranks:
            parts.append(f"1/{K + ranks[doc_id]}")
    br, vr = bm25_rank.get(doc_id, "-"), vector_rank.get(doc_id, "-")
    print(f"  {doc_id:<7}{br!s:>10}{vr!s:>13}   {' + '.join(parts):<13} = {score:.4f}")
print("""
  kb-01 is never first, but BOTH retrievers put it 2nd — and that agreement wins.
  kb-06 tops the vector list, but BM25 never found it, so it drops below every
  document both lists found. The scores never entered into it, so it does not
  matter that one list runs 0-12 and the other 0-1.""")

print("=" * 72)
print("4. WHAT k DOES")
print("=" * 72)
for k in (0, 10, 60, 1000):
    fused = reciprocal_rank_fusion([BM25, VECTOR], k=k)
    order = " > ".join(doc_id for doc_id, _ in fused)
    print(f"  k = {k:<5} rank 1 worth {1 / (k + 1):.4f}, rank 4 worth {1 / (k + 4):.4f}   {order}")
print("""
  Small k: the gap between rank 1 and rank 4 is huge, so each list's top pick
  dominates. Large k: every position is worth about the same, so it becomes "how
  many lists found you". 60 is the long-standing default and rarely worth tuning.""")

print("=" * 72)
print("5. WEIGHTS: TRUST ONE RETRIEVER MORE")
print("=" * 72)
for weights in ([1.0, 1.0], [2.0, 1.0], [1.0, 2.0]):
    fused = reciprocal_rank_fusion([BM25, VECTOR], weights=weights)
    print(f"  bm25 x{weights[0]:.0f}, vector x{weights[1]:.0f}:  "
          + " > ".join(doc_id for doc_id, _ in fused))
print("""
  Weights are the knob worth tuning: a code-search tool full of identifiers wants
  BM25 heavier; a help centre full of paraphrased questions wants vectors heavier.
  Tune them against a golden set (Exercise 2), never by feel.""")
