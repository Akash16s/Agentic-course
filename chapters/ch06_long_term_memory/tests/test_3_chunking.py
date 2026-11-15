"""Tests for Chapter 6, Exercise 3 — chunking."""

import pytest

from chapters.ch06_long_term_memory.exercises.exercise_3_chunking import chunk_text


class TestBasics:
    def test_empty(self):
        assert chunk_text("") == []
        assert chunk_text("   \n  ") == []

    def test_short_text_is_one_chunk(self):
        assert chunk_text("hello world", max_chars=100) == ["hello world"]

    def test_strips_the_input(self):
        assert chunk_text("  hello  ", max_chars=100) == ["hello"]

    def test_long_text_is_split(self):
        assert len(chunk_text("x" * 1000, max_chars=100, overlap=10)) > 1

    def test_chunks_respect_max_chars(self):
        chunks = chunk_text("word " * 500, max_chars=200, overlap=20)
        assert all(len(c) <= 200 for c in chunks)

    def test_no_empty_chunks(self):
        assert all(c.strip() for c in chunk_text("a\n\n\n\nb" * 200, max_chars=50))


class TestBoundaries:
    def test_prefers_paragraph_breaks(self):
        text = ("A" * 80) + "\n\n" + ("B" * 80)
        chunks = chunk_text(text, max_chars=100, overlap=0)
        assert chunks[0].endswith("A")

    def test_prefers_sentence_breaks(self):
        text = "First sentence here. " * 20
        chunks = chunk_text(text, max_chars=100, overlap=0)
        assert chunks[0].rstrip().endswith(".")

    def test_falls_back_to_word_breaks(self):
        text = "word " * 200
        chunks = chunk_text(text, max_chars=60, overlap=0)
        assert not any(c.startswith("ord") or c.endswith("wor") for c in chunks)

    def test_hard_cut_when_there_is_no_separator(self):
        chunks = chunk_text("x" * 500, max_chars=100, overlap=0)
        assert len(chunks) == 5


class TestOverlap:
    def test_consecutive_chunks_share_text(self):
        chunks = chunk_text("word " * 300, max_chars=200, overlap=50)
        assert len(chunks) > 2
        assert any(chunks[0][-20:] in chunks[1] for _ in [1])

    def test_a_fact_on_a_boundary_survives_somewhere(self):
        filler = "Filler sentence. " * 30
        text = filler + "The production timeout is 30 seconds. " + filler
        chunks = chunk_text(text, max_chars=300, overlap=80)
        assert any("timeout is 30 seconds" in c for c in chunks), (
            "a fact spanning a boundary must be whole in at least one chunk"
        )

    def test_zero_overlap_is_allowed(self):
        assert len(chunk_text("word " * 200, max_chars=100, overlap=0)) > 1


class TestTermination:
    def test_terminates_with_overlap_equal_to_max_chars(self):
        # the classic infinite loop: end - overlap == start, so start never advances
        chunks = chunk_text("x" * 1000, max_chars=100, overlap=100)
        assert len(chunks) < 500

    def test_terminates_with_overlap_larger_than_max_chars(self):
        chunks = chunk_text("x" * 500, max_chars=50, overlap=200)
        assert len(chunks) < 500

    def test_covers_the_whole_document(self):
        text = "".join(f"[{i}]" for i in range(200))
        chunks = chunk_text(text, max_chars=100, overlap=20)
        assert "[0]" in chunks[0]
        assert "[199]" in chunks[-1]
