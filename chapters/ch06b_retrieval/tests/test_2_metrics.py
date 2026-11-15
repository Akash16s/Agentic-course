"""Tests for Chapter 6b, Exercise 2 — retrieval metrics."""

import math

import pytest

from chapters.ch06b_retrieval.exercises.exercise_2_metrics import (
    GoldenQuery,
    QueryScore,
    RetrievalReport,
    evaluate_retriever,
    hit_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

RETRIEVED = ["a", "b", "c", "d", "e"]


def test_golden_query_stores_relevant_as_a_frozenset():
    assert GoldenQuery("q", ["a", "b", "a"]).relevant == frozenset({"a", "b"})
    assert GoldenQuery("q").relevant == frozenset()


@pytest.mark.parametrize("metric", [recall_at_k, precision_at_k, hit_at_k, ndcg_at_k])
def test_k_below_one_raises(metric):
    with pytest.raises(ValueError):
        metric(RETRIEVED, {"a"}, k=0)


@pytest.mark.parametrize("metric", [recall_at_k, precision_at_k, hit_at_k, ndcg_at_k])
def test_empty_relevant_set_is_zero_not_an_error(metric):
    assert metric(RETRIEVED, set(), k=5) == 0.0


class TestRecall:
    def test_fraction_of_relevant_found_in_the_top_k(self):
        assert recall_at_k(RETRIEVED, {"a", "c"}, k=5) == 1.0
        assert recall_at_k(RETRIEVED, {"a", "z"}, k=5) == 0.5
        assert recall_at_k(RETRIEVED, {"a", "e"}, k=3) == 0.5  # "e" is outside the top 3
        assert recall_at_k(RETRIEVED, {"z"}, k=5) == 0.0

    def test_k_larger_than_the_results(self):
        assert recall_at_k(["a", "b"], {"a", "b"}, k=10) == 1.0
        assert recall_at_k([], {"a"}, k=5) == 0.0

    def test_duplicates_are_removed_before_cutting_to_k(self):
        # ["a", "a", "b"] -> ["a", "b"]: the top 2 holds both
        assert recall_at_k(["a", "a", "b"], {"a", "b"}, k=2) == 1.0

    def test_relevant_can_be_any_iterable(self):
        assert recall_at_k(RETRIEVED, ["a", "c"], k=5) == 1.0


class TestPrecision:
    def test_fraction_of_the_top_k_that_is_relevant(self):
        assert precision_at_k(RETRIEVED, {"a", "d"}, k=5) == pytest.approx(0.4)
        assert precision_at_k(RETRIEVED, {"a", "e"}, k=2) == 0.5

    def test_divides_by_k_not_by_what_came_back(self):
        # 2 results when asked for 5: three empty slots are not relevant slots
        assert precision_at_k(["a", "b"], {"a", "b"}, k=5) == pytest.approx(0.4)

    def test_duplicates_get_no_double_credit(self):
        assert precision_at_k(["a", "a", "a"], {"a"}, k=3) == pytest.approx(1 / 3)


def test_hit_at_k_is_one_if_anything_relevant_is_in_the_top_k():
    assert hit_at_k(RETRIEVED, {"c", "z"}, k=3) == 1.0
    assert hit_at_k(RETRIEVED, {"e"}, k=3) == 0.0


class TestReciprocalRank:
    def test_one_over_the_rank_of_the_first_hit(self):
        assert reciprocal_rank(RETRIEVED, {"a"}) == 1.0
        assert reciprocal_rank(RETRIEVED, {"b"}) == 0.5
        assert reciprocal_rank(RETRIEVED, {"d"}) == 0.25
        assert reciprocal_rank(RETRIEVED, {"b", "c", "d"}) == 0.5  # first hit only

    def test_no_hit_is_zero(self):
        assert reciprocal_rank(RETRIEVED, {"z"}) == 0.0
        assert reciprocal_rank(RETRIEVED, set()) == 0.0

    def test_k_cuts_off_and_none_means_no_cut_off(self):
        assert reciprocal_rank(RETRIEVED, {"d"}, k=3) == 0.0
        long_list = [str(i) for i in range(100)]
        assert reciprocal_rank(long_list, {"99"}) == pytest.approx(0.01)

    def test_duplicates_do_not_push_the_hit_down(self):
        assert reciprocal_rank(["a", "a", "a", "b"], {"b"}) == 0.5

    def test_mean_reciprocal_rank(self):
        runs = [(RETRIEVED, {"a"}), (RETRIEVED, {"b"}), (RETRIEVED, {"z"})]
        assert mean_reciprocal_rank(runs) == pytest.approx((1 + 0.5 + 0) / 3)
        assert mean_reciprocal_rank([(RETRIEVED, {"d"})], k=3) == 0.0
        assert mean_reciprocal_rank([]) == 0.0


class TestNDCG:
    def test_perfect_ranking_is_one_and_no_hits_is_zero(self):
        assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, k=3) == pytest.approx(1.0)
        assert ndcg_at_k(RETRIEVED, {"z"}, k=5) == 0.0

    def test_hand_computed(self):
        # one relevant doc at rank 2: DCG = 1/log2(3), IDCG = 1
        assert ndcg_at_k(["x", "a"], {"a"}, k=2) == pytest.approx(1 / math.log2(3))
        # relevant at ranks 1 and 3, two relevant in total
        dcg = 1 / math.log2(2) + 1 / math.log2(4)
        idcg = 1 / math.log2(2) + 1 / math.log2(3)
        assert ndcg_at_k(["a", "x", "b"], {"a", "b"}, k=3) == pytest.approx(dcg / idcg)

    def test_higher_is_better(self):
        assert ndcg_at_k(["a", "x", "y"], {"a"}, k=3) > ndcg_at_k(["x", "y", "a"], {"a"}, k=3)

    def test_ideal_ranking_is_capped_at_k(self):
        # 3 relevant docs, k=2: a perfect top 2 must still score 1.0
        assert ndcg_at_k(["a", "b"], {"a", "b", "c"}, k=2) == pytest.approx(1.0)

    def test_duplicates_get_no_double_credit(self):
        assert ndcg_at_k(["a", "a"], {"a", "b"}, k=2) == pytest.approx(
            ndcg_at_k(["a"], {"a", "b"}, k=2))


GOLDEN = [
    GoldenQuery("refund", {"kb-04"}),
    GoldenQuery("E4012", {"kb-02"}),
    GoldenQuery("login", {"kb-06", "kb-07"}),
]

CANNED = {
    "refund": ["kb-04", "kb-01", "kb-02"],          # hit at rank 1
    "E4012": ["kb-01", "kb-03", "kb-09"],           # miss
    "login": ["kb-01", "kb-06", "kb-06", "kb-02"],  # one of two, at rank 2 (and a dupe)
}


def canned(query, k):
    return CANNED[query]


class TestEvaluateRetriever:
    def test_report_shape(self):
        report = evaluate_retriever(canned, GOLDEN, k=3)
        assert isinstance(report, RetrievalReport)
        assert (report.k, report.n, report.skipped) == (3, 3, 0)
        assert evaluate_retriever(canned, GOLDEN).k == 5

    def test_recall_mrr_and_hit_rate_are_means(self):
        report = evaluate_retriever(canned, GOLDEN, k=3)
        assert report.recall == pytest.approx((1.0 + 0.0 + 0.5) / 3)
        assert report.mrr == pytest.approx((1.0 + 0.0 + 0.5) / 3)
        assert report.hit_rate == pytest.approx(2 / 3)

    def test_precision_and_ndcg_are_means(self):
        report = evaluate_retriever(canned, GOLDEN, k=3)
        assert report.precision == pytest.approx((1 / 3 + 0 + 1 / 3) / 3)
        ndcgs = [ndcg_at_k(CANNED["refund"], {"kb-04"}, 3), 0.0,
                 ndcg_at_k(CANNED["login"], {"kb-06", "kb-07"}, 3)]
        assert report.ndcg == pytest.approx(sum(ndcgs) / 3)

    def test_per_query_scores_in_golden_order_deduplicated(self):
        report = evaluate_retriever(canned, GOLDEN, k=3)
        assert [q.query for q in report.per_query] == ["refund", "E4012", "login"]
        assert all(isinstance(q, QueryScore) for q in report.per_query)
        assert report.per_query[2].retrieved == ["kb-01", "kb-06", "kb-02"]

    def test_misses_lists_the_failed_queries(self):
        assert [q.query for q in evaluate_retriever(canned, GOLDEN, k=3).misses] == ["E4012"]

    def test_calls_the_retriever_once_per_query_with_k(self):
        calls = []

        def spy(query, k):
            calls.append((query, k))
            return CANNED[query]

        evaluate_retriever(spy, GOLDEN, k=7)
        assert calls == [("refund", 7), ("E4012", 7), ("login", 7)]

    def test_accepts_plain_pairs(self):
        assert evaluate_retriever(canned, [("refund", ["kb-04"])], k=3).recall == 1.0

    def test_queries_without_labels_are_skipped_not_scored(self):
        def guarded(query, k):
            assert query != "unlabelled", "skipped queries must not reach the retriever"
            return CANNED[query]

        report = evaluate_retriever(guarded, GOLDEN + [GoldenQuery("unlabelled")], k=3)
        assert (report.n, report.skipped) == (3, 1)
        assert report.recall == pytest.approx((1.0 + 0.0 + 0.5) / 3)

    def test_empty_golden_set(self):
        report = evaluate_retriever(canned, [], k=3)
        assert report.n == 0
        assert report.recall == report.mrr == report.ndcg == 0.0
        assert report.per_query == []
