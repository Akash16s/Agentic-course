"""EXERCISE 1 — Sessions and the store interface.

    pytest chapters/ch05_short_term_memory/tests -q -k store
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agentlib.llm import Message


@dataclass
class Session:
    """One conversation thread.

    Fields:
        session_id: str
        messages:   list[Message]     default []
        metadata:   dict[str, Any]    default {}
        created_at: float             default time.time()
        updated_at: float             default time.time()
    """

    session_id: str

    def __len__(self) -> int:
        """Number of messages."""
        # TODO: implement
        raise NotImplementedError


class SessionStore(ABC):
    """Where conversations live between requests.

    FOUR abstract methods. Resist the urge to add trimming or summarising here — a
    store that does those is a store you cannot swap, and swapping it is the whole
    point of the interface.
    """

    @abstractmethod
    def load(self, session_id: str) -> Session:
        """Return the session. An UNKNOWN id returns an EMPTY Session, never None.

        Returning None makes every caller write the same guard, and one of them will
        forget. Returning an empty session makes `store.load(id).messages` always work.
        """

    @abstractmethod
    def save(self, session: Session) -> None: ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Deleting a session that does not exist is NOT an error."""

    @abstractmethod
    def list_sessions(self) -> list[str]: ...

    def append(self, session_id: str, *messages: Message) -> Session:
        """Load, append, save, return the updated session.

        Concrete, not abstract: every store implements it identically, so it belongs
        in the base class. Copy each message (`dict(m)`) on the way in.
        """
        # TODO: implement
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    """A dict behind a lock. Perfect for tests; useless across a restart."""

    def __init__(self) -> None:
        """Set up `self._sessions: dict[str, Session]` and a `threading.Lock`."""
        # TODO: implement
        raise NotImplementedError

    def load(self, session_id: str) -> Session:
        """Return a COPY of the stored session, or a fresh empty one.

        A copy, because if you hand back the stored object, a caller who mutates it
        has written to your store without ever calling save(). That bug presents as
        "the history contains messages we never persisted" and takes hours to find.

        Copy the messages list AND each message dict.
        """
        # TODO: implement
        raise NotImplementedError

    def save(self, session: Session) -> None:
        """Store a COPY, and refresh `updated_at`."""
        # TODO: implement
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        # TODO: implement
        raise NotImplementedError

    def list_sessions(self) -> list[str]:
        """Sorted ids."""
        # TODO: implement
        raise NotImplementedError
