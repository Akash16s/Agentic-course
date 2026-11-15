"""Tests for Chapter 5, Exercise 2 — durable sessions."""

import sqlite3
import threading

import pytest

from chapters.ch05_short_term_memory.exercises.exercise_1_store import Session
from chapters.ch05_short_term_memory.exercises.exercise_2_sqlite import SQLiteSessionStore

U = {"role": "user", "content": "hi"}
A = {"role": "assistant", "content": "hello"}


@pytest.fixture
def store(tmp_path):
    return SQLiteSessionStore(str(tmp_path / "test.db"))


class TestBasics:
    def test_unknown_id_returns_empty_session(self, store):
        assert store.load("nope").messages == []

    def test_round_trip(self, store):
        store.append("a", U, A)
        loaded = store.load("a")
        assert loaded.messages == [U, A]

    def test_delete(self, store):
        store.append("a", U)
        store.delete("a")
        assert store.load("a").messages == []

    def test_delete_unknown_is_fine(self, store):
        store.delete("never")

    def test_metadata_round_trips(self, store):
        store.save(Session(session_id="a", metadata={"user": "akash", "n": 3}))
        assert store.load("a").metadata == {"user": "akash", "n": 3}

    def test_tool_messages_round_trip(self, store):
        calls = {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "t", "arguments": '{"a":1}'}}],
        }
        tool = {"role": "tool", "tool_call_id": "c1", "name": "t", "content": "ok"}
        store.append("a", calls, tool)
        assert store.load("a").messages == [calls, tool]


class TestDurability:
    def test_survives_a_new_store_object(self, tmp_path):
        path = str(tmp_path / "d.db")
        SQLiteSessionStore(path).append("a", U)
        assert len(SQLiteSessionStore(path).load("a")) == 1

    def test_two_stores_share_the_file(self, tmp_path):
        path = str(tmp_path / "d.db")
        one, two = SQLiteSessionStore(path), SQLiteSessionStore(path)
        one.append("a", U)
        assert len(two.load("a")) == 1


class TestUpsert:
    def test_save_twice_updates_rather_than_duplicating(self, store):
        store.save(Session(session_id="a", messages=[U]))
        store.save(Session(session_id="a", messages=[U, A]))
        assert len(store.load("a")) == 2
        assert store.list_sessions() == ["a"]

    def test_created_at_is_preserved_across_updates(self, store):
        store.save(Session(session_id="a", messages=[U], created_at=12345.0))
        store.append("a", A)
        assert store.load("a").created_at == 12345.0

    def test_updated_at_moves(self, store):
        store.append("a", U)
        first = store.load("a").updated_at
        store.append("a", A)
        assert store.load("a").updated_at >= first


class TestListing:
    def test_most_recently_updated_first(self, store):
        store.append("old", U)
        store.append("new", U)
        store.append("old", A)          # touch 'old' again
        assert store.list_sessions()[0] == "old"

    def test_empty(self, store):
        assert store.list_sessions() == []


class TestThreadSafety:
    def test_usable_from_several_threads(self, store):
        errors = []

        def work(i):
            try:
                store.append(f"s{i}", {"role": "user", "content": str(i)})
                store.load(f"s{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, (
            f"sharing one sqlite connection across threads: {errors[0]!r}"
        )
        assert len(store.list_sessions()) == 12
