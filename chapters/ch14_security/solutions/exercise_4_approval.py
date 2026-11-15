"""SOLUTION — Chapter 14, Exercise 4."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class ApprovalRequest:
    tool: str
    arguments: dict[str, Any]
    reason: str = ""


class ApprovalQueue:
    """Collects calls needing a human. Deliberately simple; the point is the shape.

    What matters in a real one: the human must see WHAT will happen, in terms they
    can judge. "Approve send_email?" is not a decision anyone can make. "Send an
    email to 400 recipients with subject X" is.
    """

    def __init__(self) -> None:
        self.pending: list[ApprovalRequest] = []
        self.decisions: dict[int, bool] = {}
        self._lock = threading.Lock()

    def request(self, tool: str, arguments: dict[str, Any], reason: str = "") -> int:
        with self._lock:
            self.pending.append(ApprovalRequest(tool, dict(arguments), reason))
            return len(self.pending) - 1

    def resolve(self, index: int, approved: bool) -> None:
        with self._lock:
            self.decisions[index] = approved

    def approved(self, index: int) -> bool | None:
        with self._lock:
            return self.decisions.get(index)

    def describe(self, index: int) -> str:
        request = self.pending[index]
        args = ", ".join(f"{k}={v!r}" for k, v in request.arguments.items())
        line = f"{request.tool}({args})"
        return f"{line}\n  reason: {request.reason}" if request.reason else line
