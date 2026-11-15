"""SOLUTION — Chapter 8, Exercise 1."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entry:
    """One write to the blackboard. The log is what makes a multi-agent run
    debuggable — without it you have several agents and no idea who did what."""

    key: str
    value: Any
    by: str
    at: float = field(default_factory=time.time)


class Blackboard:
    """Thread-safe shared state with an append-only audit log.

    The "blackboard" pattern: agents do not message each other, they read and write
    a shared surface. That decoupling is the point — an agent does not need to know
    who produced a fact or who will consume it.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._log: list[Entry] = []
        self._lock = threading.Lock()

    def write(self, key: str, value: Any, *, by: str = "unknown") -> None:
        with self._lock:
            self._values[key] = value
            self._log.append(Entry(key=key, value=value, by=by))

    def read(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._values

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    @property
    def log(self) -> list[Entry]:
        with self._lock:
            return list(self._log)

    def history(self, key: str) -> list[Entry]:
        """Every write to one key, oldest first. Shows overwrites — which is how you
        find two agents fighting over the same slot."""
        with self._lock:
            return [e for e in self._log if e.key == key]

    def render(self, *, max_chars: int = 400) -> str:
        """Blackboard contents for a prompt."""
        with self._lock:
            if not self._values:
                return "(nothing on the blackboard yet)"
            return "\n".join(
                f"- {key}: {str(value)[:max_chars]}"
                for key, value in self._values.items()
            )
