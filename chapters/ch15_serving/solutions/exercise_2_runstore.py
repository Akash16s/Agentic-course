"""SOLUTION — Chapter 15, Exercise 2."""

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
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Run:
    """A unit of durable work. This is the record that survives a restart."""

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
        return self.status in (RunStatus.SUCCEEDED, RunStatus.FAILED,
                               RunStatus.CANCELLED)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class RunStore:
    """Durable run state in SQLite.

    Why it matters: an agent run is minutes long. A deploy, an OOM kill or a
    rolling restart in the middle of one loses the work AND the money already
    spent, and the user sees a spinner that never resolves. A row that says
    RUNNING with a timestamp is what lets a new worker pick it up.
    """

    def __init__(self, path: str = "runs.db") -> None:
        self.path = path
        self._local = threading.local()
        with self._connect() as conn:
            conn.execute(
SCHEMA
            )

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def create(self, task: str, *, session_id: str = "default",
               run_id: str | None = None) -> Run:
        run = Run(id=run_id or uuid.uuid4().hex[:16], task=task, session_id=session_id)
        self.save(run)
        return run

    def save(self, run: Run) -> None:
        run.updated_at = time.time()
        conn = self._connect()
        with conn:
            conn.execute(
                """INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       status=excluded.status, output=excluded.output,
                       error=excluded.error, steps=excluded.steps,
                       cost=excluded.cost, updated_at=excluded.updated_at,
                       attempts=excluded.attempts""",
                (run.id, run.task, run.session_id, run.status.value, run.output,
                 run.error, run.steps, run.cost, run.created_at, run.updated_at,
                 run.attempts),
            )

    def get(self, run_id: str) -> Run | None:
        row = self._connect().execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, *, session_id: str | None = None, limit: int = 50) -> list[Run]:
        if session_id is None:
            rows = self._connect().execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._connect().execute(
                "SELECT * FROM runs WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT ?", (session_id, limit)
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def reclaim_stale(self, *, older_than_s: float = 300.0,
                      max_attempts: int = 3) -> list[Run]:
        """Find RUNNING rows nobody has touched and requeue or fail them.

        This is crash recovery. A worker that died mid-run left a row saying
        RUNNING forever; without this the user waits for something that will never
        finish. `max_attempts` stops a run that reliably kills its worker from
        killing every worker in turn — the poison-pill problem.
        """
        cutoff = time.time() - older_than_s
        rows = self._connect().execute(
            "SELECT * FROM runs WHERE status = ? AND updated_at < ?",
            (RunStatus.RUNNING.value, cutoff),
        ).fetchall()

        reclaimed: list[Run] = []
        for row in rows:
            run = self._from_row(row)
            if run.attempts >= max_attempts:
                run.status = RunStatus.FAILED
                run.error = f"abandoned after {run.attempts} attempts"
            else:
                run.status = RunStatus.QUEUED
            self.save(run)
            reclaimed.append(run)
        return reclaimed

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"], task=row["task"], session_id=row["session_id"],
            status=RunStatus(row["status"]), output=row["output"],
            error=row["error"], steps=row["steps"], cost=row["cost"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            attempts=row["attempts"],
        )
