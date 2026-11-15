"""EXERCISE 2 — Durable sessions in SQLite.

WHY: SQLite is not a toy. One file, no server, real transactions, and it comfortably
outlasts the traffic most agents ever see. It is the correct default, and "we'll need
Postgres" is usually a guess.

    pytest chapters/ch05_short_term_memory/tests -q -k sqlite
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

from .exercise_1_store import Session, SessionStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    messages   TEXT NOT NULL,
    metadata   TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""


class SQLiteSessionStore(SessionStore):
    """Sessions in one SQLite file.

    Design note — ONE JSON BLOB PER SESSION, not one row per message. We always read
    and write whole conversations, so a blob is one query where rows would be N. Flip
    to rows when you need to query *inside* conversations (Chapter 6's problem).
    """

    def __init__(self, path: str = "sessions.db") -> None:
        """Store `path`, set up `threading.local()`, and run SCHEMA once."""
        # TODO: implement
        raise NotImplementedError

    def _connect(self) -> sqlite3.Connection:
        """Return THIS THREAD's connection, creating it on first use.

        sqlite3 connections are not thread-safe. Sharing one across a thread pool
        raises:

            ProgrammingError: SQLite objects created in a thread can only be used
            in that same thread

        and it only happens under concurrency, which means it only happens in
        production. `threading.local()` costs one attribute lookup and removes the
        entire class of bug.

        Set `conn.row_factory = sqlite3.Row` so rows are subscriptable by name.
        """
        # TODO: implement
        raise NotImplementedError

    def load(self, session_id: str) -> Session:
        """SELECT the row; missing -> an empty Session. json.loads the two blobs."""
        # TODO: implement
        raise NotImplementedError

    def save(self, session: Session) -> None:
        """UPSERT.

        Use `INSERT ... ON CONFLICT(session_id) DO UPDATE SET ...` — one statement,
        atomic. A SELECT-then-INSERT-or-UPDATE is two statements and a race.

        Keep the original `created_at`; set `updated_at` to now.
        Wrap in `with conn:` so it commits (or rolls back on an exception).
        """
        # TODO: implement
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        # TODO: implement
        raise NotImplementedError

    def list_sessions(self) -> list[str]:
        """Ids, MOST RECENTLY UPDATED FIRST. That is the order a UI wants."""
        # TODO: implement
        raise NotImplementedError
