"""Tests for Chapter 6b, Exercise 1 — BM25."""

import math

import pytest

from chapters.ch06b_retrieval.exercises.exercise_1_bm25 import BM25Index

# The worked example from the README, section 3.
TINY = {
    "d1": "reset your password from the login page",
    "d2": "error E4012 means the card was declined",
    "d3": "card payments fail when the card has expired or the card is blocked",
}

KB = {
    "kb-01": "Payment errors: what each error means and what to do when a payment error appears.",
    "kb-02": "Card declined at the terminal. If the terminal shows E4012, the issuing bank "
             "refused the charge: ask the customer for another card.",
    "kb-03": "Error E4013 means the card has expired. Ask for a different card.",
    "kb-04": "How to issue a refund from the dashboard.",
    "kb-05": "The payments API returns an error code in the error field of every failed response.",
    "kb-06": "Login error after a password reset: clear the browser cache.",
}


@pytest.fixture
def tiny():
    index = BM25Index()
    index.add_many(TINY.items())
    return index


@pytest.fixture
def kb():
    index = BM25Index()
    index.add_many(KB.items())
    return index


class TestConstruction:
    def test_defaults_and_custom_parameters(self):
        assert (BM25Index().k1, BM25Index().b) == (1.5, 0.75)
        assert (BM25Index(k1=1.2, b=0.5).k1, BM25Index(k1=1.2, b=0.5).b) == (1.2, 0.5)

    def test_invalid_parameters_raise(self):
        with pytest.raises(ValueError):
            BM25Index(k1=-0.1)
        with pytest.raises(ValueError):
            BM25Index(b=-0.1)
        with pytest.raises(ValueError):
            BM25Index(b=1.1)

    def test_custom_tokenizer_is_used(self):
        index = BM25Index(tokenizer=lambda text: text.split("|"))
        index.add("a", "x y|z")
        assert index.search("x y")[0][0] == "a"
        assert index.search("x") == []


class TestIndexing:
    def test_empty_index(self):
        index = BM25Index()
        assert len(index) == 0
        assert index.avgdl == 0.0

    def test_len_contains_and_get(self, tiny):
        assert len(tiny) == 3
        assert "d1" in tiny and "nope" not in tiny
        assert tiny.get("d2") == TINY["d2"]
        assert tiny.get("nope") is None

    def test_avgdl_counts_tokens_after_stopword_removal(self, tiny):
        # d1 = 4 tokens, d2 = 5, d3 = 7  ->  16 / 3
        assert tiny.avgdl == pytest.approx(16 / 3)

    def test_readding_an_id_replaces_it(self):
        index = BM25Index()
        index.add("a", "refund policy")
        index.add("b", "shipping")
        idf_before = index.idf("refund")
        index.add("a", "refund policy")
        assert index.idf("refund") == pytest.approx(idf_before), "df counted twice"
        index.add("a", "warranty terms")
        assert len(index) == 2
        assert index.search("refund") == []
        assert index.search("warranty")[0][0] == "a"

    def test_remove(self, tiny):
        assert tiny.remove("d3") is True
        assert tiny.remove("nope") is False
        assert len(tiny) == 2 and "d3" not in tiny
        assert tiny.search("blocked") == []
        assert tiny.avgdl == pytest.approx(9 / 2)  # d1 + d2 = 4 + 5

    def test_empty_text_is_allowed(self):
        index = BM25Index()
        index.add("empty", "")
        index.add("a", "refund policy")
        assert len(index) == 2
        assert [doc_id for doc_id, _ in index.search("refund")] == ["a"]


class TestIDF:
    def test_unknown_term_is_zero(self, tiny):
        assert tiny.idf("zebra") == 0.0

    def test_matches_the_smoothed_formula(self, tiny):
        # "card" is in 2 of 3 documents
        assert tiny.idf("card") == pytest.approx(math.log(1 + (3 - 2 + 0.5) / (2 + 0.5)))

    def test_rare_terms_score_higher(self, tiny):
        assert tiny.idf("declined") > tiny.idf("card")

    def test_never_negative_even_for_a_term_in_every_document(self):
        # the unsmoothed formula goes negative here, so matching a common word would
        # push a document BELOW one that did not match at all
        index = BM25Index()
        for i in range(10):
            index.add(str(i), f"card number {i}")
        assert index.idf("card") > 0

    def test_counts_documents_not_occurrences(self):
        repeated, single = BM25Index(), BM25Index()
        repeated.add_many([("a", "card card card card"), ("b", "refund"), ("c", "shipping")])
        single.add_many([("a", "card"), ("b", "refund"), ("c", "shipping")])
        assert repeated.idf("card") == pytest.approx(single.idf("card"))


class TestScore:
    def test_worked_example_from_the_readme(self, tiny):
        assert tiny.score("card declined", "d2") == pytest.approx(1.4928, abs=1e-3)
        assert tiny.score("card declined", "d3") == pytest.approx(0.7266, abs=1e-3)

    def test_zero_without_a_matching_term_or_for_an_unknown_doc(self, tiny):
        assert tiny.score("card declined", "d1") == 0.0
        assert tiny.score("card", "nope") == 0.0

    def test_repeated_query_terms_count_once(self, tiny):
        assert tiny.score("card card card", "d3") == pytest.approx(tiny.score("card", "d3"))

    def test_query_is_tokenised_like_documents(self, tiny):
        assert tiny.score("CARD, Declined!", "d2") == pytest.approx(
            tiny.score("card declined", "d2"))

    def test_tf_saturates(self):
        # 1 -> 2 mentions is a big jump; 10 -> 11 is nearly nothing
        def score_with(tf):
            index = BM25Index(b=0.0)  # switch off length normalisation
            index.add("x", " ".join(["refund"] * tf))
            index.add("y", "shipping")
            return index.score("refund", "x")

        assert score_with(2) - score_with(1) > 10 * (score_with(11) - score_with(10))

    def test_tf_part_never_exceeds_k1_plus_one(self):
        index = BM25Index(b=0.0)
        index.add("x", " ".join(["refund"] * 1000))
        index.add("y", "shipping")
        assert index.score("refund", "x") < index.idf("refund") * (index.k1 + 1)

    def test_k1_zero_makes_tf_irrelevant(self):
        index = BM25Index(k1=0.0)
        index.add_many([("once", "refund policy"), ("many", "refund refund refund policy"),
                        ("other", "shipping")])
        assert index.score("refund", "once") == pytest.approx(index.score("refund", "many"))

    def test_length_normalisation_prefers_the_shorter_document(self):
        long_text = "refund policy plus many other words about shipping returns warranties"
        normalised, flat = BM25Index(), BM25Index(b=0.0)
        for index in (normalised, flat):
            index.add_many([("short", "refund policy"), ("long", long_text)])
        assert normalised.score("refund", "short") > normalised.score("refund", "long")
        # b = 0 switches it off
        assert flat.score("refund", "short") == pytest.approx(flat.score("refund", "long"))

    def test_all_empty_documents_do_not_divide_by_zero(self):
        index = BM25Index()
        index.add_many([("a", ""), ("b", "")])
        assert index.score("anything", "a") == 0.0
        assert index.search("anything") == []


class TestSearch:
    def test_finds_the_rare_identifier(self, kb):
        # the whole reason BM25 is in this chapter
        assert kb.search("error E4012", k=1)[0][0] == "kb-02"

    def test_returns_doc_id_score_pairs_best_first(self, tiny):
        results = tiny.search("card declined")
        assert [doc_id for doc_id, _ in results] == ["d2", "d3"]
        for doc_id, score in results:
            assert score == pytest.approx(tiny.score("card declined", doc_id))

    def test_respects_k(self, kb, tiny):
        assert len(kb.search("error card", k=2)) == 2
        assert len(tiny.search("card", k=50)) == 2  # only 2 documents match
        assert tiny.search("card", k=0) == []
        assert tiny.search("card", k=-1) == []

    def test_nothing_matched_returns_nothing(self, tiny):
        # BM25 can honestly say "nothing matched"; vector search cannot
        assert tiny.search("zebra giraffe") == []
        assert tiny.search("") == []
        assert BM25Index().search("anything") == []

    def test_ties_keep_insertion_order(self):
        index = BM25Index()
        index.add_many([("first", "refund"), ("second", "refund"), ("third", "shipping")])
        assert [doc_id for doc_id, _ in index.search("refund")] == ["first", "second"]

    def test_no_stemming_errors_is_not_error(self):
        # a known limitation, worth seeing once: tokenise does not stem
        index = BM25Index()
        index.add_many([("a", "payment errors"), ("b", "shipping")])
        assert index.search("error") == []
