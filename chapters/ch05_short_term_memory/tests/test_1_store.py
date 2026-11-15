"""Tests for Chapter 5, Exercise 1 — sessions and the in-memory store."""

import pytest

from chapters.ch05_short_term_memory.exercises.exercise_1_store import (
    InMemorySessionStore,
    Session,
    SessionStore,
)

U = {"role": "user", "content": "hi"}
A = {"role": "assistant", "content": "hello"}


class TestSession:
    def test_defaults(self):
        s = Session(session_id="x")
        assert s.messages == []
        assert s.metadata == {}
        assert s.created_at > 0
        assert s.updated_at > 0

    def test_len(self):
        assert len(Session(session_id="x", messages=[U, A])) == 2

    def test_defaults_are_not_shared(self):
        a, b = Session(session_id="a"), Session(session_id="b")
        a.messages.append(U)
        assert b.messages == [], "mutable default leaked between instances"


class TestInterface:
    def test_cannot_instantiate_the_abstract_base(self):
        with pytest.raises(TypeError):
            SessionStore()


class TestInMemoryStore:
    def test_unknown_id_returns_an_empty_session_not_none(self):
        s = InMemorySessionStore().load("nope")
        assert isinstance(s, Session)
        assert s.session_id == "nope"
        assert s.messages == []

    def test_save_then_load(self):
        store = InMemorySessionStore()
        store.save(Session(session_id="a", messages=[U, A]))
        assert len(store.load("a")) == 2

    def test_append(self):
        store = InMemorySessionStore()
        store.append("a", U)
        store.append("a", A)
        assert [m["role"] for m in store.load("a").messages] == ["user", "assistant"]

    def test_append_several_at_once(self):
        store = InMemorySessionStore()
        store.append("a", U, A)
        assert len(store.load("a")) == 2

    def test_append_returns_the_session(self):
        store = InMemorySessionStore()
        assert len(store.append("a", U)) == 1

    def test_sessions_are_independent(self):
        store = InMemorySessionStore()
        store.append("a", U)
        store.append("b", A)
        assert len(store.load("a")) == 1
        assert store.load("b").messages[0]["role"] == "assistant"

    def test_delete(self):
        store = InMemorySessionStore()
        store.append("a", U)
        store.delete("a")
        assert store.load("a").messages == []

    def test_delete_unknown_is_not_an_error(self):
        InMemorySessionStore().delete("never-existed")

    def test_list_sessions(self):
        store = InMemorySessionStore()
        store.append("b", U)
        store.append("a", U)
        assert store.list_sessions() == ["a", "b"]

    def test_list_is_empty_initially(self):
        assert InMemorySessionStore().list_sessions() == []


class TestIsolation:
    def test_load_returns_a_copy_of_the_list(self):
        store = InMemorySessionStore()
        store.append("a", U)
        store.load("a").messages.append(A)
        assert len(store.load("a")) == 1, "mutating a loaded session wrote to the store"

    def test_load_returns_copies_of_the_messages(self):
        store = InMemorySessionStore()
        store.append("a", U)
        store.load("a").messages[0]["content"] = "tampered"
        assert store.load("a").messages[0]["content"] == "hi"

    def test_save_stores_a_copy(self):
        store = InMemorySessionStore()
        session = Session(session_id="a", messages=[dict(U)])
        store.save(session)
        session.messages.append(A)
        assert len(store.load("a")) == 1, "the store kept a reference to the caller's list"

    def test_appended_messages_are_copied(self):
        store = InMemorySessionStore()
        message = {"role": "user", "content": "original"}
        store.append("a", message)
        message["content"] = "changed"
        assert store.load("a").messages[0]["content"] == "original"
