"""Short-term memory — conversation state that survives the process.

Promoted from Chapter 5.

Chapter 1's `Conversation` lives in RAM and dies with the process. This adds:
  * a `SessionStore` interface, with in-memory and SQLite implementations
  * memory *strategies* that decide what the model actually sees
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from agentlib.context import compact, message_pairs, trim_messages
from agentlib.llm import Message
from agentlib.tokens import estimate_messages_tokens

# ------------------------------------------------------------------- records


@dataclass
class Session:
    """One conversation thread, identified by `session_id`."""

    session_id: str
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __len__(self) -> int:
        return len(self.messages)


# --------------------------------------------------------------------- store


class SessionStore(ABC):
    """Where conversations live between requests.

    Deliberately tiny. A store that also trims, summarises or counts tokens is a store
    you cannot swap, and swapping it (memory -> SQLite -> Redis -> Postgres) is the
    whole point of having the interface.
    """

    @abstractmethod
    def load(self, session_id: str) -> Session: ...

    @abstractmethod
    def save(self, session: Session) -> None: ...

    @abstractmethod
    def delete(self, session_id: str) -> None: ...

    @abstractmethod
    def list_sessions(self) -> list[str]: ...

    def append(self, session_id: str, *messages: Message) -> Session:
        """Load, append, save. The common path."""
        session = self.load(session_id)
        session.messages.extend(dict(m) for m in messages)
        session.updated_at = time.time()
        self.save(session)
        return session


class InMemorySessionStore(SessionStore):
    """A dict. Perfect for tests, useless across a restart or across two workers."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def load(self, session_id: str) -> Session:
        with self._lock:
            found = self._sessions.get(session_id)
            if found is None:
                return Session(session_id=session_id)
            # deep-ish copy so callers cannot mutate stored state by accident
            return Session(
                session_id=found.session_id,
                messages=[dict(m) for m in found.messages],
                metadata=dict(found.metadata),
                created_at=found.created_at,
                updated_at=found.updated_at,
            )

    def save(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.session_id] = Session(
                session_id=session.session_id,
                messages=[dict(m) for m in session.messages],
                metadata=dict(session.metadata),
                created_at=session.created_at,
                updated_at=time.time(),
            )

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        with self._lock:
            return sorted(self._sessions)


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
                """CREATE TABLE IF NOT EXISTS sessions (
                       session_id TEXT PRIMARY KEY,
                       messages   TEXT NOT NULL,
                       metadata   TEXT NOT NULL,
                       created_at REAL NOT NULL,
                       updated_at REAL NOT NULL
                   )"""
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


# ---------------------------------------------------------------- strategies


class MemoryStrategy(ABC):
    """Decides what the model SEES, given everything that was said.

    Storage keeps the full record; the strategy produces the view. Keeping these
    separate means you can change the strategy without losing history, and replay an
    old conversation under a new strategy — which you will want in Chapter 11.
    """

    @abstractmethod
    def build(self, messages: list[Message]) -> list[Message]: ...


class FullHistory(MemoryStrategy):
    """Send everything. Correct until it isn't."""

    def build(self, messages: list[Message]) -> list[Message]:
        return list(messages)


class SlidingWindow(MemoryStrategy):
    """Keep the first `keep_first` and last `keep_last` groups within a token budget."""

    def __init__(self, max_tokens: int, *, keep_first: int = 1, keep_last: int = 6) -> None:
        self.max_tokens = max_tokens
        self.keep_first = keep_first
        self.keep_last = keep_last

    def build(self, messages: list[Message]) -> list[Message]:
        return trim_messages(
            messages,
            self.max_tokens,
            keep_first=self.keep_first,
            keep_last=self.keep_last,
        )


class SummaryBuffer(MemoryStrategy):
    """Compact once the history crosses a threshold, then cache the summary.

    The cache is what makes this affordable: without it you pay for a summarisation
    call on every single turn, which can cost more than the conversation it is saving.
    """

    def __init__(
        self,
        summarise: Callable[[str], str],
        *,
        max_tokens: int,
        keep_recent: int = 4,
        threshold: float = 0.7,
        min_compact_groups: int = 4,
    ) -> None:
        self.summarise = summarise
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.threshold = threshold
        self.min_compact_groups = min_compact_groups
        self._summary: str | None = None
        self._summarised_upto = 0   # index into `messages` already folded in

    @property
    def summary(self) -> str | None:
        return self._summary

    def build(self, messages: list[Message]) -> list[Message]:
        tail = messages[self._summarised_upto:]
        view = self._with_summary(tail)

        # Measure the VIEW, not the full history. After the first compaction the full
        # history is permanently over budget, so measuring it would re-summarise on
        # every single turn forever.
        if estimate_messages_tokens(view) <= self.max_tokens * self.threshold:
            return view

        # Don't pay for an API call to fold one message away. Wait for a batch.
        groups = message_pairs(tail)
        if len(groups) - self.keep_recent < self.min_compact_groups:
            return view

        def summarise_with_carry(transcript: str) -> str:
            if self._summary:
                transcript = f"PREVIOUS SUMMARY:\n{self._summary}\n\n{transcript}"
            return self.summarise(transcript)

        compacted = compact(tail, summarise_with_carry, keep_recent=self.keep_recent)
        # compacted[0] is the summary marker; everything after is verbatim recent
        self._summary = compacted[0]["content"].split("\n", 1)[-1]
        self._summarised_upto = len(messages) - (len(compacted) - 1)
        return compacted

    def _with_summary(self, tail: list[Message]) -> list[Message]:
        if not self._summary:
            return list(tail)
        marker: Message = {
            "role": "user",
            "content": f"[Summary of the earlier conversation]\n{self._summary}",
        }
        return [marker] + list(tail)
