"""Tests for Chapter 6, Exercise 1 — vectors and similarity."""

import math

import pytest

from chapters.ch06_long_term_memory.exercises.exercise_1_similarity import (
    CachedEmbedder,
    Embedder,
    HashingEmbedder,
    cosine_similarity,
    dot,
    l2_normalise,
    tokenise,
)


class TestTokenise:
    def test_lowercases_and_splits(self):
        assert tokenise("Hello WORLD", drop_stopwords=False) == ["hello", "world"]

    def test_drops_punctuation(self):
        assert tokenise("hi, there!", drop_stopwords=False) == ["hi", "there"]

    def test_keeps_apostrophes(self):
        assert "don't" in tokenise("don't stop", drop_stopwords=False)

    def test_drops_stopwords(self):
        assert tokenise("the cat on the mat") == ["cat", "mat"]

    def test_keeps_stopwords_when_asked(self):
        assert tokenise("the cat", drop_stopwords=False) == ["the", "cat"]

    def test_all_stopword_query_is_not_emptied(self):
        # an empty vector matches nothing, which is worse than a weak match
        assert tokenise("what is it") != []

    def test_empty(self):
        assert tokenise("") == []


class TestL2Normalise:
    def test_unit_length(self):
        out = l2_normalise([3.0, 4.0])
        assert math.isclose(math.sqrt(sum(x * x for x in out)), 1.0)

    def test_direction_preserved(self):
        assert l2_normalise([3.0, 4.0]) == pytest.approx([0.6, 0.8])

    def test_already_normalised(self):
        assert l2_normalise([1.0, 0.0]) == pytest.approx([1.0, 0.0])

    def test_zero_vector_does_not_divide_by_zero(self):
        assert l2_normalise([0.0, 0.0]) == [0.0, 0.0]

    def test_returns_a_new_list(self):
        original = [0.0, 0.0]
        assert l2_normalise(original) is not original


class TestCosine:
    def test_identical(self):
        assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite(self):
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_ignores_magnitude(self):
        # the whole reason we use cosine: a short note and a long essay on the same
        # topic point the same way
        assert cosine_similarity([1, 1], [100, 100]) == pytest.approx(1.0)

    def test_zero_vector_returns_zero_not_an_error(self):
        assert cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_both_zero(self):
        assert cosine_similarity([0, 0], [0, 0]) == 0.0

    def test_dimension_mismatch_raises(self):
        # usually means two different embedding models; must be loud
        with pytest.raises(ValueError):
            cosine_similarity([1, 2], [1, 2, 3])

    def test_dot(self):
        assert dot([1, 2, 3], [4, 5, 6]) == 32


class TestHashingEmbedder:
    def test_dimensions(self):
        assert len(HashingEmbedder(dimensions=64).embed("hello")) == 64

    def test_output_is_normalised(self):
        v = HashingEmbedder().embed("some text here")
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, abs_tol=1e-9)

    def test_deterministic_within_a_process(self):
        e = HashingEmbedder()
        assert e.embed("hello world") == e.embed("hello world")

    def test_deterministic_across_instances(self):
        # `hash()` is randomised per process; blake2b is not. Using hash() would mean
        # stored vectors stop matching after a restart.
        assert HashingEmbedder().embed("hello") == HashingEmbedder().embed("hello")

    def test_identical_text_is_perfectly_similar(self):
        e = HashingEmbedder()
        assert cosine_similarity(e.embed("a cat"), e.embed("a cat")) == pytest.approx(1.0)

    def test_shared_words_score_higher_than_none(self):
        e = HashingEmbedder()
        base = e.embed("postgres database migration")
        related = cosine_similarity(base, e.embed("postgres migration plan"))
        unrelated = cosine_similarity(base, e.embed("buy milk and eggs"))
        assert related > unrelated

    def test_unrelated_text_scores_near_zero(self):
        e = HashingEmbedder()
        score = cosine_similarity(e.embed("postgres database"), e.embed("buy milk"))
        assert score < 0.1

    def test_empty_text_gives_a_zero_vector(self):
        assert HashingEmbedder().embed("") == [0.0] * 1024

    def test_bigrams_capture_word_order(self):
        with_bigrams = HashingEmbedder(bigrams=True)
        without = HashingEmbedder(bigrams=False)
        a, b = "dog bites man", "man bites dog"
        assert cosine_similarity(without.embed(a), without.embed(b)) == pytest.approx(1.0)
        assert cosine_similarity(with_bigrams.embed(a), with_bigrams.embed(b)) < 1.0

    def test_batch_matches_single(self):
        e = HashingEmbedder()
        assert e.embed_batch(["a b", "c d"]) == [e.embed("a b"), e.embed("c d")]

    def test_lexical_only_is_the_known_limitation(self):
        # "car" and "automobile" mean the same thing and share no characters.
        # A real embedding model scores this ~0.9; a hashing one scores 0.
        e = HashingEmbedder()
        assert cosine_similarity(e.embed("car"), e.embed("automobile")) == 0.0


class TestCachedEmbedder:
    def test_caches_repeats(self):
        c = CachedEmbedder(HashingEmbedder())
        c.embed("hello")
        c.embed("hello")
        assert c.misses == 1
        assert c.hits == 1

    def test_returns_the_same_vector(self):
        c = CachedEmbedder(HashingEmbedder())
        assert c.embed("hello") == c.embed("hello")

    def test_different_texts_both_miss(self):
        c = CachedEmbedder(HashingEmbedder())
        c.embed("a")
        c.embed("b")
        assert c.misses == 2

    def test_exposes_inner_dimensions(self):
        assert CachedEmbedder(HashingEmbedder(dimensions=64)).dimensions == 64

    def test_batch_only_embeds_the_misses(self):
        class Counting(HashingEmbedder):
            def __init__(self):
                super().__init__()
                self.embedded = []

            def embed_batch(self, texts):
                self.embedded.extend(texts)
                return super().embed_batch(texts)

        inner = Counting()
        c = CachedEmbedder(inner)
        c.embed_batch(["a", "b"])
        c.embed_batch(["b", "c"])
        assert inner.embedded == ["a", "b", "c"], "cached texts were re-embedded"

    def test_batch_preserves_order(self):
        c = CachedEmbedder(HashingEmbedder())
        c.embed("b")
        out = c.embed_batch(["a", "b", "c"])
        assert out[1] == c.embed("b")

    def test_eviction_keeps_the_cache_bounded(self):
        c = CachedEmbedder(HashingEmbedder(), max_size=2)
        for text in "abcdef":
            c.embed(text)
        assert len(c._cache) <= 2
