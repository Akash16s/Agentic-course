"""Tests for Chapter 6b, Exercise 3 — fusion and hybrid search."""

import pytest

from agentlib.embeddings import HashingEmbedder
from agentlib.memory.vector import VectorStore
from chapters.ch06b_retrieval.exercises.exercise_1_bm25 import BM25Index
from chapters.ch06b_retrieval.exercises.exercise_3_hybrid import (
    HybridHit,
    HybridRetriever,
    reciprocal_rank_fusion,
)


def ids(fused):
    return [doc_id for doc_id, _ in fused]


class TestReciprocalRankFusion:
    def test_single_ranking_keeps_its_order(self):
        assert ids(reciprocal_rank_fusion([["a", "b", "c"]])) == ["a", "b", "c"]

    def test_score_formula(self):
        fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60))
        assert fused["a"] == pytest.approx(1 / 61)
        assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
        assert fused["c"] == pytest.approx(1 / 62)

    def test_found_by_both_beats_first_in_one(self):
        # "c" is never first, but both lists found it
        fused = reciprocal_rank_fusion([["a", "c", "x"], ["b", "c", "y"]])
        assert ids(fused)[0] == "c"

    def test_scores_are_ignored(self):
        # a huge BM25 score must not let one list dominate
        bm25 = [("a", 950.0), ("b", 0.3)]
        vector = [("b", 0.91), ("a", 0.10)]
        fused = dict(reciprocal_rank_fusion([bm25, vector]))
        assert fused["a"] == pytest.approx(fused["b"])

    def test_accepts_ids_pairs_and_objects_with_doc_id(self):
        hits = [HybridHit("c", 0.5), HybridHit("a", 0.4)]
        fused = reciprocal_rank_fusion([["a", "b"], [("b", 3.0), ("d", 1.0)], hits])
        assert set(ids(fused)) == {"a", "b", "c", "d"}
        scores = [s for _, s in fused]
        assert scores == sorted(scores, reverse=True)

    def test_duplicate_within_one_list_counts_once(self):
        fused = dict(reciprocal_rank_fusion([["a", "a", "b"]], k=60))
        assert fused["a"] == pytest.approx(1 / 61)
        # the duplicate does not use up a rank: "b" is still rank 2
        assert fused["b"] == pytest.approx(1 / 62)

    def test_ties_keep_first_seen_order(self):
        assert ids(reciprocal_rank_fusion([["a", "b"], ["b", "a"]])) == ["a", "b"]

    def test_weights(self):
        fused = dict(reciprocal_rank_fusion([["a"], ["b"]], weights=[2.0, 1.0], k=60))
        assert fused["a"] == pytest.approx(2 / 61)
        assert fused["b"] == pytest.approx(1 / 61)
        rankings = [["a", "b"], ["b", "a"]]
        assert ids(reciprocal_rank_fusion(rankings, weights=[1.0, 3.0]))[0] == "b"

    def test_small_k_lets_one_list_dominate(self):
        # k=0: rank 1 is worth 1.0 and rank 2 only 0.5, so "a" (first in one
        # list, absent from the other) beats "c" (second in both)
        rankings = [["a", "c"], ["b", "c"]]
        assert ids(reciprocal_rank_fusion(rankings, k=0))[0] == "a"
        assert ids(reciprocal_rank_fusion(rankings, k=60))[0] == "c"

    def test_bad_arguments_raise(self):
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([["a"], ["b"]], weights=[1.0])
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([["a"]], k=-1)

    def test_nothing_to_fuse(self):
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []


KB = {
    "kb-01": "Payment errors: what each error means and what to do when a payment error appears.",
    "kb-02": "Card declined at the terminal. Most declines are temporary and clear on retry. "
             "If the terminal shows E4012, the issuing bank refused the charge: ask the "
             "customer for another card. Check the network connection and the terminal "
             "firmware before escalating.",
    "kb-03": "Error E4013 means the card has expired. Ask for a different card.",
    "kb-04": "How to issue a refund from the dashboard.",
    "kb-05": "The payments API returns an error code in the error field of every failed response.",
    "kb-06": "Login error after a password reset: clear the browser cache.",
    "kb-07": "Webhook delivery errors are retried for 24 hours.",
    "kb-08": "Payout schedule: funds arrive in your bank account within two business days.",
    "kb-09": "Rate limit error 429: slow down and retry with backoff.",
    "kb-10": "Terminal setup: pair the card reader over Bluetooth.",
}


@pytest.fixture
def hybrid():
    h = HybridRetriever(VectorStore(HashingEmbedder()), BM25Index())
    h.add_many(KB.items(), metadatas=[{"n": i} for i in range(len(KB))])
    return h


class TestHybridRetrieverSetup:
    def test_stores_its_parts(self):
        vs, bm = VectorStore(HashingEmbedder()), BM25Index()
        h = HybridRetriever(vs, bm, rrf_k=10, weights=(0.5, 2.0))
        assert h.vector_store is vs and h.bm25 is bm
        assert (h.rrf_k, h.weights) == (10, (0.5, 2.0))
        default = HybridRetriever(vs, bm)
        assert (default.rrf_k, default.weights) == (60, (1.0, 1.0))

    def test_add_writes_to_both_indexes(self):
        h = HybridRetriever(VectorStore(HashingEmbedder()), BM25Index())
        h.add("x", "refund policy", metadata={"source": "faq"})
        assert "x" in h.vector_store
        assert "x" in h.bm25
        assert h.vector_store.get("x").metadata == {"source": "faq"}

    def test_add_many_writes_to_both_indexes(self, hybrid):
        assert len(hybrid.vector_store) == len(KB)
        assert len(hybrid.bm25) == len(KB)
        empty = HybridRetriever(VectorStore(HashingEmbedder()), BM25Index())
        empty.add_many([])
        assert len(empty.vector_store) == 0

    def test_add_many_uses_one_embedding_batch(self):
        class Counting(HashingEmbedder):
            batches = 0

            def embed_batch(self, texts):
                Counting.batches += 1
                return super().embed_batch(texts)

        h = HybridRetriever(VectorStore(Counting()), BM25Index())
        h.add_many(KB.items())
        assert Counting.batches == 1


class TestHybridSearch:
    def test_returns_k_hybrid_hits(self, hybrid):
        hits = hybrid.search("refund", k=3)
        assert len(hits) == 3
        assert all(isinstance(h, HybridHit) for h in hits)
        assert hybrid.search("card", k=0) == []

    def test_finds_the_error_code_vector_search_misses(self, hybrid):
        # vector search alone (HashingEmbedder) does not put kb-02 in its top 5...
        vector_top5 = [r.document.id for r in hybrid.vector_store.search("error E4012", k=5)]
        assert "kb-02" not in vector_top5
        # ...but fused with BM25 it makes the top 5
        assert "kb-02" in hybrid.search_ids("error E4012", k=5)

    def test_hits_carry_text_and_a_copy_of_the_metadata(self, hybrid):
        hit = hybrid.search("refund dashboard", k=1)[0]
        assert hit.doc_id == "kb-04"
        assert hit.text == KB["kb-04"]
        assert hit.metadata == {"n": 3}
        hit.metadata["n"] = 99
        assert hybrid.vector_store.get("kb-04").metadata == {"n": 3}

    def test_reports_the_rank_in_each_list(self, hybrid):
        hit = next(h for h in hybrid.search("error E4012", k=10) if h.doc_id == "kb-02")
        assert hit.bm25_rank == 1
        assert hit.vector_rank is not None and hit.vector_rank > 5

    def test_bm25_rank_is_none_when_bm25_did_not_find_it(self, hybrid):
        hits = hybrid.search("refund dashboard", k=10)
        no_keyword_match = [h for h in hits if h.doc_id == "kb-09"]
        assert no_keyword_match and no_keyword_match[0].bm25_rank is None

    def test_scores_are_the_rrf_scores(self, hybrid):
        hits = hybrid.search("error E4012", k=3, candidates=10)
        vector_ids = [r.document.id for r in hybrid.vector_store.search("error E4012", k=10)]
        bm25_ids = hybrid.bm25.search("error E4012", k=10)
        expected = reciprocal_rank_fusion([vector_ids, bm25_ids], k=60)[:3]
        assert [(h.doc_id, pytest.approx(h.score)) for h in hits] == expected

    def test_candidates_limit_what_each_side_returns(self, hybrid):
        spy = []
        original = hybrid.bm25.search
        hybrid.bm25.search = lambda q, k=10: spy.append(k) or original(q, k)
        hybrid.search("error E4012", k=3, candidates=20)
        hybrid.search("error E4012", k=5, candidates=1)  # raised to k
        assert spy == [20, 5]

    def test_weights_shift_the_result(self):
        def build(weights):
            h = HybridRetriever(VectorStore(HashingEmbedder()), BM25Index(), weights=weights)
            h.add_many(KB.items())
            return h

        bm25_heavy = build((0.1, 1.0)).search_ids("error E4012", k=1)
        assert bm25_heavy == ["kb-02"]

    def test_search_ids(self, hybrid):
        assert hybrid.search_ids("refund dashboard", k=2) == [
            h.doc_id for h in hybrid.search("refund dashboard", k=2)]
        empty = HybridRetriever(VectorStore(HashingEmbedder()), BM25Index())
        assert empty.search_ids("anything") == []
