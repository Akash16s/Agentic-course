"""SOLUTION — Chapter 5, Exercise 2."""

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
    """Durable sessions in one file. Good to surprisingly large scale.

    Messages are stored as a JSON blob rather than one row per message. That is the
    right trade here: we always read and write a whole conversation, never a single
    message, and a blob makes that one query instead of N.
    """

    def __init__(self, path: str = "sessions.db") -> None:
        self.path = path
        self._local = threading.local()
        with self._connect() as conn:
            conn.execute(
                SCHEMA
            )

    def _connect(self) -> sqlite3.Connection:
        # sqlite connections are not thread-safe; one per thread
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def load(self, session_id: str) -> Session:
        row = self._connect().execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return Session(session_id=session_id)
        return Session(
            session_id=row["session_id"],
            messages=json.loads(row["messages"]),
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save(self, session: Session) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                """INSERT INTO sessions
                       (session_id, messages, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                       messages = excluded.messages,
                       metadata = excluded.metadata,
                       updated_at = excluded.updated_at""",
                (
                    session.session_id,
                    json.dumps(session.messages),
                    json.dumps(session.metadata),
                    session.created_at,
                    time.time(),
                ),
            )

    def delete(self, session_id: str) -> None:
        conn = self._connect()
        with conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def list_sessions(self) -> list[str]:
        rows = self._connect().execute(
            "SELECT session_id FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [r["session_id"] for r in rows]
