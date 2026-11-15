"""EXERCISE 2 — Durable run state.

    pytest chapters/ch15_serving/tests -q -k runstore
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, task TEXT NOT NULL,
    session_id TEXT NOT NULL, status TEXT NOT NULL,
    output TEXT NOT NULL, error TEXT,
    steps INTEGER NOT NULL, cost REAL NOT NULL,
    created_at REAL NOT NULL, updated_at REAL NOT NULL,
    attempts INTEGER NOT NULL
)
"""


class RunStatus(str, Enum):
    """QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Run:
    """The record that survives a restart.

    Fields: id, task, session_id="default", status=QUEUED, output="",
            error=None, steps=0, cost=0.0, created_at=now, updated_at=now,
            attempts=0
    """

    id: str
    task: str
    session_id: str = "default"
    status: RunStatus = RunStatus.QUEUED
    output: str = ""
    error: str | None = None
    steps: int = 0
    cost: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    attempts: int = 0

    @property
    def terminal(self) -> bool:
        """SUCCEEDED, FAILED or CANCELLED."""
        # TODO: implement
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """asdict(), with `status` as its string value so it JSON-serialises."""
        # TODO: implement
        raise NotImplementedError


class RunStore:
    """Durable run state in SQLite.

    Same thread-local connection pattern as Chapter 5 — sqlite connections are not
    thread-safe, and this one is read by web handlers and written by workers.
    """

    def __init__(self, path: str = "runs.db") -> None:
        # TODO: implement (create the table)
        raise NotImplementedError

    def _connect(self) -> sqlite3.Connection:
        """This thread's connection, with `row_factory = sqlite3.Row`."""
        # TODO: implement
        raise NotImplementedError

    def create(self, task: str, *, session_id: str = "default",
               run_id: str | None = None) -> Run:
        """Build a QUEUED Run (id defaults to uuid4().hex[:16]), save, return it."""
        # TODO: implement
        raise NotImplementedError

    def save(self, run: Run) -> None:
        """UPSERT, refreshing `updated_at` to now.

        `updated_at` is load-bearing: `reclaim_stale` uses it as the heartbeat that
        tells a dead worker from a slow one. Forget to refresh it and every long
        run looks abandoned.
        """
        # TODO: implement
        raise NotImplementedError

    def get(self, run_id: str) -> Run | None:
        # TODO: implement
        raise NotImplementedError

    def list(self, *, session_id: str | None = None, limit: int = 50) -> list[Run]:
        """Newest first; optionally filtered by session."""
        # TODO: implement
        raise NotImplementedError

    def reclaim_stale(self, *, older_than_s: float = 300.0,
                      max_attempts: int = 3) -> list[Run]:
        """Crash recovery. Return the runs that were reclaimed.

        Spec:
          * find rows with status RUNNING and updated_at < now - older_than_s
          * attempts >= max_attempts -> FAILED, error "abandoned after N attempts"
          * otherwise                -> back to QUEUED
          * save each, return them

        WHY THIS EXISTS: a worker that is OOM-killed mid-run leaves a row saying
        RUNNING forever. The user watches a spinner for something that will never
        finish, and the money is already spent.

        WHY max_attempts IS NOT OPTIONAL: a run that reliably crashes its worker
        will crash every worker in turn — the poison-pill problem. It takes down
        the fleet one pod at a time, and the failure looks like an infrastructure
        problem rather than one bad input.
        """
        # TODO: implement
        raise NotImplementedError
