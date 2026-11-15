"""Tests for Chapter 6, Exercise 4 — ranking."""

import time

import pytest

from chapters.ch06_long_term_memory.exercises.exercise_2_vector_store import Document
from chapters.ch06_long_term_memory.exercises.exercise_4_scoring import (
    DEFAULT_HALF_LIFE_S,
    Memory,
    MemoryKind,
    composite_score,
    recency_weight,
)

DAY = 24 * 3600


class TestMemoryKind:
    def test_three_kinds(self):
        assert {k.value for k in MemoryKind} == {"semantic", "episodic", "procedural"}

    def test_string_comparison(self):
        assert MemoryKind.EPISODIC == "episodic"


class TestMemory:
    def test_defaults(self):
        m = Memory(text="x")
        assert m.kind is MemoryKind.SEMANTIC
        assert m.subject == "default"
        assert m.importance == 0.5
        assert m.use_count == 0
        assert m.id

    def test_ids_are_unique(self):
        assert Memory(text="a").id != Memory(text="b").id

    def test_to_metadata_is_json_safe(self):
        import json

        json.dumps(Memory(text="x", kind=MemoryKind.EPISODIC).to_metadata())

    def test_to_metadata_stores_kind_as_a_string(self):
        assert Memory(text="x", kind=MemoryKind.EPISODIC).to_metadata()["kind"] == "episodic"

    def test_round_trip_through_a_document(self):
        original = Memory(text="hello", kind=MemoryKind.PROCEDURAL,
                          subject="akash", importance=0.9, source="chat")
        document = Document(id=original.id, text=original.text,
                            embedding=[], metadata=original.to_metadata())
        restored = Memory.from_document(document)
        assert restored.text == "hello"
        assert restored.kind is MemoryKind.PROCEDURAL
        assert restored.subject == "akash"
        assert restored.importance == 0.9
        assert restored.id == original.id

    def test_from_document_tolerates_missing_keys(self):
        # stored data outlives your code
        m = Memory.from_document(Document(id="x", text="t", embedding=[], metadata={}))
        assert m.kind is MemoryKind.SEMANTIC

    def test_from_document_tolerates_an_unknown_kind(self):
        document = Document(id="x", text="t", embedding=[],
                            metadata={"kind": "telepathic"})
        assert Memory.from_document(document).kind is MemoryKind.SEMANTIC


class TestRecencyWeight:
    def test_brand_new(self):
        assert recency_weight(0) == 1.0

    def test_negative_age_is_clamped(self):
        assert recency_weight(-100) == 1.0

    def test_one_half_life(self):
        assert recency_weight(DEFAULT_HALF_LIFE_S) == pytest.approx(0.5)

    def test_two_half_lives(self):
        assert recency_weight(2 * DEFAULT_HALF_LIFE_S) == pytest.approx(0.25)

    def test_custom_half_life(self):
        assert recency_weight(DAY, half_life_s=DAY) == pytest.approx(0.5)

    def test_monotonically_decreasing(self):
        values = [recency_weight(d * DAY) for d in range(0, 40, 5)]
        assert values == sorted(values, reverse=True)

    def test_never_reaches_zero(self):
        # exponential, not linear-with-cutoff: old memories become unlikely, not
        # impossible
        assert recency_weight(365 * DAY) > 0


class TestCompositeScore:
    def test_similarity_dominates(self):
        now = time.time()
        high = Memory(text="a", created_at=now)
        low = Memory(text="b", created_at=now)
        assert composite_score(0.9, high, now=now) > composite_score(0.1, low, now=now)

    def test_importance_breaks_a_similarity_tie(self):
        now = time.time()
        important = Memory(text="a", importance=1.0, created_at=now)
        trivial = Memory(text="b", importance=0.0, created_at=now)
        assert composite_score(0.5, important, now=now) > composite_score(0.5, trivial, now=now)

    def test_episodic_memories_decay(self):
        now = time.time()
        fresh = Memory(text="a", kind=MemoryKind.EPISODIC, created_at=now)
        stale = Memory(text="b", kind=MemoryKind.EPISODIC, created_at=now - 90 * DAY)
        assert composite_score(0.5, fresh, now=now) > composite_score(0.5, stale, now=now)

    def test_semantic_memories_do_not_decay(self):
        now = time.time()
        fresh = Memory(text="a", kind=MemoryKind.SEMANTIC, created_at=now)
        old = Memory(text="b", kind=MemoryKind.SEMANTIC, created_at=now - 365 * DAY)
        assert composite_score(0.5, fresh, now=now) == pytest.approx(
            composite_score(0.5, old, now=now)
        ), "a fact about someone's job is not less true for being a year old"

    def test_procedural_memories_do_not_decay(self):
        now = time.time()
        old = Memory(text="b", kind=MemoryKind.PROCEDURAL, created_at=now - 365 * DAY)
        assert composite_score(0.5, old, now=now) == pytest.approx(
            composite_score(0.5, Memory(text="a", kind=MemoryKind.PROCEDURAL,
                                        created_at=now), now=now)
        )

    def test_recency_beats_a_small_similarity_edge(self):
        # the motivating example from the chapter
        now = time.time()
        stale = Memory(text="favourite colour is blue",
                       kind=MemoryKind.EPISODIC, created_at=now - 90 * DAY)
        current = Memory(text="changed their mind, it's green",
                         kind=MemoryKind.EPISODIC, created_at=now)
        assert composite_score(0.79, current, now=now) > composite_score(0.82, stale, now=now)

    def test_weights_are_configurable(self):
        now = time.time()
        m = Memory(text="a", importance=1.0, created_at=now)
        only_similarity = composite_score(
            0.5, m, now=now, w_similarity=1.0, w_recency=0.0, w_importance=0.0
        )
        assert only_similarity == pytest.approx(0.5)
