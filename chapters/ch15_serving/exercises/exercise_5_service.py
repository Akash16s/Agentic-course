"""EXERCISE 5 — A real agent service.

No automated test. Needs your key and `pip install fastapi uvicorn` (already in
your .venv).

    uvicorn chapters.ch15_serving.exercises.exercise_5_service:app --reload

BUILD
  POST /runs                 {"task": "...", "session_id": "..."} -> 202 {"run_id"}
  GET  /runs/{id}            -> the run as JSON
  GET  /runs/{id}/stream     -> SSE: progress events, then the answer, then [DONE]
  GET  /runs?session_id=...  -> recent runs for a session
  POST /runs/{id}/cancel     -> mark CANCELLED
  GET  /healthz              -> {"ok": true, "queue_depth": n}

WIRE IN what you already have:
  - Chapter 5   SQLiteSessionStore, keyed by session_id
  - Chapter 12  a tracer per request; return the trace_id in a response header
  - Chapter 13  a per-session rate limiter and budget guard
  - Chapter 14  a PermissionPolicy on the tools
  - this chapter: RunStore + JobQueue + SSE

THEN THE PARTS THAT ARE ACTUALLY THE EXERCISE

  1. SSE, done properly
       a. Stream a long answer. Confirm the browser (or `curl -N`) renders tokens
          as they arrive, not all at once.
       b. Now REMOVE the trailing blank line from your frames. Watch it hang.
          Sit with it for a minute — this is the bug you want to recognise instantly.
       c. Kill the provider mid-stream (point at a bad base_url after 2 seconds).
          Confirm your client sees an `error` event and not a silent truncation.
       d. Remove the [DONE] sentinel. Watch the browser reconnect and re-run the
          whole agent. Note the doubled cost.

  2. Durability
       a. Submit a 60-second run. Kill the process (`kill -9`) at 20 seconds.
       b. Restart. Call `reclaim_stale()` on startup. Confirm the run is requeued
          and completes.
       c. Make a task that reliably crashes the worker. Confirm max_attempts stops
          it after N tries instead of taking out every worker in turn.
       d. Implement graceful shutdown on SIGTERM: stop accepting, drain in-flight,
          exit. Compare what a deploy does to live runs with and without it.

  3. Concurrency
       a. Fire 50 concurrent requests (`hey`, `ab`, or an asyncio script).
          Measure p50 and p99 latency, and the error rate.
       b. Add `time.sleep(2)` inside one tool, in an ASYNC handler. Measure again.
          Explain the p99 to yourself before you read your own notes.
       c. Fix it with `asyncio.to_thread`. Measure a third time.
       d. Drop max_queued to 5 and fire 50 requests. Confirm you get fast 503s
          rather than slow successes, and decide which you would rather ship.

  4. Multi-user correctness
       a. Two sessions, interleaved requests. Confirm histories never mix.
       b. Try to GET another session's run id. If it works, you have just written
          the data breach from section 6. Fix it.
       c. Give one session a $0.01 budget and confirm the other is unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# TODO: from fastapi import FastAPI, HTTPException
# TODO: from fastapi.responses import StreamingResponse
# TODO: app = FastAPI()


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
