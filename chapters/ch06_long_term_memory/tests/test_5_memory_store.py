"""Tests for Chapter 6, Exercise 5 — the memory store."""

import time

import pytest

from chapters.ch06_long_term_memory.exercises.exercise_1_similarity import HashingEmbedder
from chapters.ch06_long_term_memory.exercises.exercise_4_scoring import (
    Memory,
    MemoryKind,
)
from chapters.ch06_long_term_memory.exercises.exercise_5_memory_store import MemoryStore

DAY = 24 * 3600


@pytest.fixture
def store():
    return MemoryStore(HashingEmbedder())


class TestRemember:
    def test_stores(self, store):
        m = store.remember("Akash prefers Python over JavaScript", subject="akash")
        assert m is not None
        assert len(store) == 1

    def test_returns_the_memory(self, store):
        m = store.remember("Akash works at Kryptos", subject="akash", importance=0.9)
        assert m.text == "Akash works at Kryptos"
        assert m.subject == "akash"
        assert m.importance == 0.9

    def test_empty_text_is_rejected(self, store):
        assert store.remember("") is None
        assert store.remember("   ") is None
        assert len(store) == 0

    def test_text_is_stripped(self, store):
        assert store.remember("  spaced  ").text == "spaced"

    def test_kind_is_recorded(self, store):
        m = store.remember("We chose Postgres", kind=MemoryKind.EPISODIC)
        assert m.kind is MemoryKind.EPISODIC


class TestDeduplication:
    def test_exact_duplicate_is_dropped(self, store):
        store.remember("Akash prefers Python", subject="akash")
        assert store.remember("Akash prefers Python", subject="akash") is None
        assert len(store) == 1

    def test_different_facts_both_stored(self, store):
        store.remember("Akash prefers Python", subject="akash")
        store.remember("Akash lives in Bangalore", subject="akash")
        assert len(store) == 2

    def test_dedup_is_scoped_to_the_subject(self, store):
        # two users may legitimately share a fact
        store.remember("prefers Python", subject="akash")
        assert store.remember("prefers Python", subject="someone-else") is not None
        assert len(store) == 2

    def test_threshold_is_configurable(self):
        loose = MemoryStore(HashingEmbedder(), dedup_threshold=2.0)  # never dedup
        loose.remember("same fact")
        loose.remember("same fact")
        assert len(loose) == 2

    def test_forty_copies_is_the_failure_it_prevents(self, store):
        for _ in range(40):
            store.remember("The user is called Akash", subject="akash")
        assert len(store) == 1


class TestRecall:
    def test_finds_a_relevant_memory(self, store):
        store.remember("Postgres is the production database", subject="a")
        store.remember("Coffee is served in the kitchen", subject="a")
        results = store.recall("production database postgres", subject="a", k=1)
        assert "Postgres" in results[0].text

    def test_scoped_to_the_subject(self, store):
        store.remember("Akash prefers Python", subject="akash")
        store.remember("Sam prefers Python", subject="sam")
        results = store.recall("prefers Python", subject="akash", k=5)
        assert all(m.subject == "akash" for m in results)
        assert len(results) == 1

    def test_respects_k(self, store):
        for i in range(10):
            store.remember(f"database fact number {i}", subject="a")
        assert len(store.recall("database fact", subject="a", k=3)) == 3

    def test_filters_by_kind(self, store):
        store.remember("database is Postgres", subject="a", kind=MemoryKind.SEMANTIC)
        store.remember("database migration ran Tuesday", subject="a",
                       kind=MemoryKind.EPISODIC)
        results = store.recall("database", subject="a", kinds=[MemoryKind.EPISODIC])
        assert len(results) == 1
        assert results[0].kind is MemoryKind.EPISODIC

    def test_empty_store(self, store):
        assert store.recall("anything") == []

    def test_min_similarity_excludes_noise(self, store):
        store.remember("Postgres is the database", subject="a")
        assert store.recall("medieval poetry", subject="a", min_similarity=0.3) == []

    def test_recency_reorders_episodic_memories(self, store):
        now = time.time()
        store.remember("colour preference is blue", subject="a",
                       kind=MemoryKind.EPISODIC, now=now - 120 * DAY)
        store.remember("colour preference changed to green", subject="a",
                       kind=MemoryKind.EPISODIC, now=now)
        top = store.recall("colour preference", subject="a", k=1, now=now)[0]
        assert "green" in top.text, "the stale fact outranked the current one"

    def test_importance_promotes(self, store):
        store.remember("database note trivial", subject="a", importance=0.0)
        store.remember("database note critical", subject="a", importance=1.0)
        top = store.recall("database note", subject="a", k=1)[0]
        assert "critical" in top.text


class TestTouch:
    def test_use_count_increments(self, store):
        store.remember("Postgres is the database", subject="a")
        store.recall("postgres database", subject="a")
        store.recall("postgres database", subject="a")
        assert store.all_memories("a")[0].use_count == 2

    def test_touch_can_be_disabled(self, store):
        store.remember("Postgres is the database", subject="a")
        store.recall("postgres database", subject="a", touch=False)
        assert store.all_memories("a")[0].use_count == 0

    def test_last_used_at_moves(self, store):
        now = time.time()
        store.remember("Postgres is the database", subject="a", now=now - 1000)
        store.recall("postgres database", subject="a", now=now)
        assert store.all_memories("a")[0].last_used_at == pytest.approx(now)


class TestUpdateAndForget:
    def test_update_replaces_the_text(self, store):
        m = store.remember("Akash works at Acme", subject="akash")
        updated = store.update(m.id, "Akash works at Kryptos")
        assert updated.text == "Akash works at Kryptos"
        assert len(store) == 1, "a changed fact must REPLACE, not sit beside, the old one"

    def test_update_keeps_the_id(self, store):
        m = store.remember("old text", subject="a")
        assert store.update(m.id, "new text").id == m.id

    def test_update_keeps_the_metadata(self, store):
        m = store.remember("old", subject="a", importance=0.9,
                           kind=MemoryKind.PROCEDURAL)
        updated = store.update(m.id, "new")
        assert updated.importance == 0.9
        assert updated.kind is MemoryKind.PROCEDURAL

    def test_update_is_searchable_by_the_new_text(self, store):
        m = store.remember("Akash works at Acme Corporation", subject="a")
        store.update(m.id, "Akash works at Kryptos on crypto tax")
        top = store.recall("kryptos crypto tax", subject="a", k=1)
        assert "Kryptos" in top[0].text

    def test_update_missing_returns_none(self, store):
        assert store.update("nope", "text") is None

    def test_forget(self, store):
        m = store.remember("temporary", subject="a")
        assert store.forget(m.id) is True
        assert len(store) == 0

    def test_forget_missing(self, store):
        assert store.forget("nope") is False


class TestAsContext:
    def test_empty(self, store):
        assert store.as_context([]) == ""

    def test_renders_with_kinds(self, store):
        memories = [
            Memory(text="Akash prefers Python", kind=MemoryKind.SEMANTIC),
            Memory(text="We chose Postgres", kind=MemoryKind.EPISODIC),
        ]
        out = store.as_context(memories)
        assert "Akash prefers Python" in out
        assert "semantic" in out and "episodic" in out

    def test_custom_header(self, store):
        out = store.as_context([Memory(text="x")], header="Known facts")
        assert out.startswith("Known facts:")


class TestAllMemories:
    def test_everything(self, store):
        store.remember("one", subject="a")
        store.remember("two", subject="b")
        assert len(store.all_memories()) == 2

    def test_filtered(self, store):
        store.remember("one", subject="a")
        store.remember("two", subject="b")
        assert len(store.all_memories("a")) == 1
