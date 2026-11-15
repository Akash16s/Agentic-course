"""SOLUTION — Chapter 5, Exercise 1."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agentlib.llm import Message


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
