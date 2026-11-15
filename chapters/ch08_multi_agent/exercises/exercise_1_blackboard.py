"""EXERCISE 1 — The blackboard.

    pytest chapters/ch08_multi_agent/tests -q -k blackboard
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entry:
    """One write. Fields: key: str, value: Any, by: str, at: float = time.time()"""

    key: str
    value: Any
    by: str


class Blackboard:
    """Thread-safe shared state with an APPEND-ONLY audit log.

    Agents read and write here instead of messaging each other. That decoupling is
    the point: an agent does not need to know who produced a fact or who consumes it.
    """

    def __init__(self) -> None:
        """`self._values: dict`, `self._log: list[Entry]`, a threading.Lock."""
        # TODO: implement
        raise NotImplementedError

    def write(self, key: str, value: Any, *, by: str = "unknown") -> None:
        """Set the value AND append to the log. Both, under the lock.

        Overwriting is allowed — that is the point of a shared surface. The log is
        what makes the overwrite visible afterwards.
        """
        # TODO: implement
        raise NotImplementedError

    def read(self, key: str, default: Any = None) -> Any:
        # TODO: implement
        raise NotImplementedError

    def has(self, key: str) -> bool:
        # TODO: implement
        raise NotImplementedError

    def all(self) -> dict[str, Any]:
        """A COPY of the current values."""
        # TODO: implement
        raise NotImplementedError

    @property
    def log(self) -> list[Entry]:
        """A COPY of the full log, oldest first."""
        # TODO: implement
        raise NotImplementedError

    def history(self, key: str) -> list[Entry]:
        """Every write to one key, oldest first.

        This is how you catch the characteristic blackboard bug: two agents
        overwriting each other's work. The final state shows one value and looks
        fine; the history shows the fight.
        """
        # TODO: implement
        raise NotImplementedError

    def render(self, *, max_chars: int = 400) -> str:
        """Current contents for a prompt.

        Empty -> "(nothing on the blackboard yet)".
        Otherwise one line per key: "- {key}: {value truncated to max_chars}".
        Truncate: this goes into a context window and an agent may have written a
        50KB document to it.
        """
        # TODO: implement
        raise NotImplementedError
