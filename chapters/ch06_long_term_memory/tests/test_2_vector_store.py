"""Tests for Chapter 6, Exercise 2 — the vector store."""

import pytest

from chapters.ch06_long_term_memory.exercises.exercise_1_similarity import HashingEmbedder
from chapters.ch06_long_term_memory.exercises.exercise_2_vector_store import (
    Document,
    VectorStore,
)

DOCS = [
    "Postgres 16 is our primary production database",
    "Redis handles session caching and rate limiting",
    "The billing service runs on Kubernetes",
    "Our frontend is React with TypeScript",
]
KINDS = [{"team": "infra"}, {"team": "infra"}, {"team": "infra"}, {"team": "web"}]


@pytest.fixture
def store():
    s = VectorStore(HashingEmbedder())
    s.add_many(DOCS, metadatas=KINDS)
    return s


class TestWriting:
    def test_add_one(self):
        s = VectorStore(HashingEmbedder())
        doc = s.add("hello")
        assert len(s) == 1
        assert doc.text == "hello"
        assert doc.id
        assert len(doc.embedding) == 1024

    def test_add_with_explicit_id(self):
        s = VectorStore(HashingEmbedder())
        assert s.add("hello", doc_id="my-id").id == "my-id"
        assert "my-id" in s

    def test_add_with_metadata(self):
        s = VectorStore(HashingEmbedder())
        assert s.add("hello", metadata={"k": "v"}).metadata == {"k": "v"}

    def test_metadata_is_copied(self):
        s = VectorStore(HashingEmbedder())
        meta = {"k": "v"}
        doc = s.add("hello", metadata=meta)
        meta["k"] = "changed"
        assert doc.metadata["k"] == "v"

    def test_add_many(self, store):
        assert len(store) == 4

    def test_add_many_empty(self):
        assert VectorStore(HashingEmbedder()).add_many([]) == []

    def test_add_many_uses_one_batch_call(self):
        class Counting(HashingEmbedder):
            calls = 0

            def embed_batch(self, texts):
                Counting.calls += 1
                return super().embed_batch(texts)

        s = VectorStore(Counting())
        s.add_many(["a", "b", "c", "d"])
        assert Counting.calls == 1, "batching is the whole point of add_many"

    def test_same_id_overwrites(self):
        s = VectorStore(HashingEmbedder())
        s.add("first", doc_id="x")
        s.add("second", doc_id="x")
        assert len(s) == 1
        assert s.get("x").text == "second"


class TestReading:
    def test_get(self, store):
        doc = store.documents[0]
        assert store.get(doc.id) is doc

    def test_get_missing(self, store):
        assert store.get("nope") is None

    def test_contains(self, store):
        assert store.documents[0].id in store
        assert "nope" not in store

    def test_documents(self, store):
        assert len(store.documents) == 4

    def test_delete(self, store):
        doc_id = store.documents[0].id
        assert store.delete(doc_id) is True
        assert len(store) == 3

    def test_delete_missing_returns_false(self, store):
        assert store.delete("nope") is False

    def test_clear(self, store):
        store.clear()
        assert len(store) == 0


class TestSearch:
    def test_finds_the_relevant_document(self, store):
        results = store.search("production database postgres", k=1)
        assert "Postgres" in results[0].text

    def test_returns_at_most_k(self, store):
        assert len(store.search("database", k=2)) <= 2

    def test_sorted_by_score_descending(self, store):
        scores = [r.score for r in store.search("database caching", k=4)]
        assert scores == sorted(scores, reverse=True)

    def test_result_exposes_text_and_metadata(self, store):
        r = store.search("typescript react frontend", k=1)[0]
        assert "React" in r.text
        assert r.metadata["team"] == "web"

    def test_empty_store(self):
        assert VectorStore(HashingEmbedder()).search("anything") == []

    def test_min_score_filters_irrelevant_results(self, store):
        # without a floor, the nearest neighbour of ANY query is still something,
        # and the model will cite it
        assert store.search("medieval poetry chromodynamics", k=5, min_score=0.3) == []
        assert len(store.search("medieval poetry chromodynamics", k=5)) > 0

    def test_where_filters_before_scoring(self, store):
        results = store.search(
            "database", k=5, where=lambda d: d.metadata["team"] == "web"
        )
        assert all(r.metadata["team"] == "web" for r in results)

    def test_where_excluding_everything(self, store):
        assert store.search("database", where=lambda d: False) == []

    def test_search_by_vector(self, store):
        vector = store.embedder.embed("postgres production database")
        assert "Postgres" in store.search_by_vector(vector, k=1)[0].text


class TestPersistence:
    def test_round_trip(self, store, tmp_path):
        path = str(tmp_path / "store.json")
        store.save(path)

        loaded = VectorStore(HashingEmbedder())
        loaded.load(path)

        assert len(loaded) == len(store)
        assert {d.text for d in loaded.documents} == set(DOCS)

    def test_search_works_after_loading(self, store, tmp_path):
        path = str(tmp_path / "store.json")
        store.save(path)
        loaded = VectorStore(HashingEmbedder())
        loaded.load(path)
        assert "Postgres" in loaded.search("postgres production database", k=1)[0].text

    def test_metadata_survives(self, store, tmp_path):
        path = str(tmp_path / "store.json")
        store.save(path)
        loaded = VectorStore(HashingEmbedder())
        loaded.load(path)
        assert {d.metadata["team"] for d in loaded.documents} == {"infra", "web"}

    def test_load_replaces_existing_contents(self, store, tmp_path):
        path = str(tmp_path / "store.json")
        store.save(path)
        other = VectorStore(HashingEmbedder())
        other.add("something else")
        other.load(path)
        assert len(other) == 4
