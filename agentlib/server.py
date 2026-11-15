"""Serving — putting an agent behind an API that several people can use at once.

Promoted from Chapter 15.

Everything so far ran in one process, for one user, and died when you pressed
Ctrl-C. This is the gap between that and something you can point traffic at.

The pieces here are framework-free on purpose: SSE framing, a job queue, and
durable run state are all just data. The FastAPI wiring is ~40 lines on top and
lives in the chapter's examples.
"""

from __future__ import annotations

import asyncio
import json
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Iterator

# --------------------------------------------------------- server-sent events


def sse(data: Any, *, event: str | None = None, id: str | None = None) -> str:
    """Format one Server-Sent Event frame.

    The format is small and unforgiving:
      * "field: value\\n" lines, then a BLANK LINE to end the frame
      * multi-line data needs a "data: " prefix PER LINE
      * the blank line is what flushes it to the browser; forget it and the client
        hangs forever with the bytes sitting in a buffer

    Non-string data is JSON-encoded, which is what you want for structured events.
    """
    lines: list[str] = []
    if event is not None:
        lines.append(f"event: {event}")
    if id is not None:
        lines.append(f"id: {id}")
    payload = data if isinstance(data, str) else json.dumps(data)
    for line in payload.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


def sse_done() -> str:
    """The conventional terminator. Browsers reconnect on a bare stream close,
    so you send an explicit sentinel and the client stops on it."""
    return sse("[DONE]", event="done")


def sse_error(message: str) -> str:
    """An error mid-stream.

    You cannot change the HTTP status after the first byte, so a failure halfway
    through a stream has to be *in* the stream. Clients must handle this event or
    a mid-stream failure looks like a truncated answer.
    """
    return sse({"error": message}, event="error")


# ------------------------------------------------------------------- runs


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
                """CREATE TABLE IF NOT EXISTS runs (
                       id TEXT PRIMARY KEY, task TEXT NOT NULL,
                       session_id TEXT NOT NULL, status TEXT NOT NULL,
                       output TEXT NOT NULL, error TEXT,
                       steps INTEGER NOT NULL, cost REAL NOT NULL,
                       created_at REAL NOT NULL, updated_at REAL NOT NULL,
                       attempts INTEGER NOT NULL
                   )"""
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


# ------------------------------------------------------------------- queue


class JobQueue:
    """An in-process work queue with a bounded buffer and N worker threads.

    BOUNDED on purpose. An unbounded queue turns a traffic spike into unbounded
    memory growth and a latency curve that goes vertical — users wait ten minutes
    for a request that should have been refused in ten milliseconds. Back-pressure
    (rejecting when full) is kinder than accepting work you cannot do.

    In production this is Redis, SQS or a database table. The semantics you need
    are the same, which is why building the small one is worth an hour.
    """

    def __init__(
        self,
        handler: Callable[[Run], None],
        store: RunStore,
        *,
        workers: int = 2,
        max_queued: int = 100,
    ) -> None:
        self.handler = handler
        self.store = store
        self.max_queued = max_queued
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=max_queued)
        self._threads: list[threading.Thread] = []
        self._running = False
        self.workers = workers

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for index in range(self.workers):
            thread = threading.Thread(target=self._work, name=f"worker-{index}",
                                      daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Ask every worker to finish and wait briefly.

        A `None` sentinel per worker, rather than a flag, so a worker blocked on
        `get()` wakes up immediately instead of after its poll interval.
        """
        self._running = False
        for _ in self._threads:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    def submit(self, task: str, *, session_id: str = "default") -> Run:
        """Enqueue work. Raises `queue.Full` rather than blocking when saturated."""
        run = self.store.create(task, session_id=session_id)
        try:
            self._queue.put_nowait(run.id)
        except queue.Full:
            run.status = RunStatus.FAILED
            run.error = "queue is full; try again shortly"
            self.store.save(run)
            raise
        return run

    def _work(self) -> None:
        while self._running:
            try:
                run_id = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if run_id is None:
                self._queue.task_done()
                return
            try:
                self._process(run_id)
            finally:
                self._queue.task_done()

    def _process(self, run_id: str) -> None:
        run = self.store.get(run_id)
        if run is None or run.status is RunStatus.CANCELLED:
            return
        run.status = RunStatus.RUNNING
        run.attempts += 1
        self.store.save(run)
        try:
            self.handler(run)
        except Exception as exc:  # noqa: BLE001 - one bad job must not kill a worker
            run.status = RunStatus.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
        else:
            if not run.terminal:
                run.status = RunStatus.SUCCEEDED
        self.store.save(run)


# ------------------------------------------------------------------- async


class AsyncLLMClient:
    """The async twin of `LLMClient`.

    Why async for serving: an agent spends nearly all its wall-clock waiting on
    someone else's network. One thread per concurrent run wastes megabytes each
    and caps you in the low hundreds; one event loop handles thousands of waiting
    requests on one core.

    The rule that keeps it working: NEVER call a blocking function inside a
    coroutine. One `requests.get` or one `time.sleep` in a tool freezes the entire
    loop — every other user's request stops. Use `asyncio.to_thread` for anything
    blocking you cannot rewrite.
    """

    def __init__(self, model: str | None = None, *, api_key: str | None = None,
                 base_url: str | None = None, timeout: float = 60.0) -> None:
        import os

        from openai import AsyncOpenAI

        from agentlib.llm import DEFAULT_MODEL, OPENROUTER_BASE_URL

        self.model = model or DEFAULT_MODEL
        self._client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url=base_url or OPENROUTER_BASE_URL,
            timeout=timeout,
            max_retries=0,
        )

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        from agentlib.llm import LLMResponse, Usage, _translate

        try:
            raw = await self._client.chat.completions.create(
                model=kwargs.pop("model", None) or self.model,
                messages=messages,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc

        choice = raw.choices[0]
        usage = raw.usage
        return LLMResponse(
            text=choice.message.content or "",
            finish_reason=choice.finish_reason or "stop",
            usage=Usage(getattr(usage, "prompt_tokens", 0) or 0,
                        getattr(usage, "completion_tokens", 0) or 0),
            model=raw.model,
            raw=raw,
        )


async def gather_bounded(coros: list[Any], *, limit: int = 8) -> list[Any]:
    """`asyncio.gather` with a concurrency cap.

    Plain `gather` on 500 coroutines opens 500 connections at once, which is how
    you rate-limit yourself into a wall. A semaphore is four lines and turns that
    into a queue.
    """
    semaphore = asyncio.Semaphore(limit)

    async def run(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(run(c) for c in coros))
