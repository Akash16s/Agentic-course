"""SSE framing bugs, and what a crash does to a run. Free and offline.

    python chapters/ch15_serving/examples/01_sse_and_durability.py
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.server import (
    JobQueue,
    RunStatus,
    RunStore,
    sse,
    sse_done,
    sse_error,
)

print("=" * 76)
print("1. SSE FRAMING — three bugs that look like your server hanging")
print("=" * 76)


def parse_stream(raw: str) -> list[str]:
    """What a browser's EventSource actually does: split on BLANK LINES."""
    frames = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        data = "\n".join(line[6:] for line in block.split("\n")
                         if line.startswith("data: "))
        frames.append(data)
    return frames


good = sse({"text": "Hello"}, event="delta") + sse({"text": " world"}, event="delta")
print(f"  correct framing      -> {len(parse_stream(good))} frames "
      f"{parse_stream(good)}")

missing_blank = good.replace("\n\n", "\n")
print(f"  one newline, not two -> {len(parse_stream(missing_blank))} frames  "
      "<- the client waits forever for a frame that never ends")

multiline_wrong = 'data: {"a": 1,\n"b": 2}\n\n'
print(f"  no per-line prefix   -> {parse_stream(multiline_wrong)}  "
      "<- silently truncated at the newline")

print(f"\n  a correct multi-line frame: {sse('two' + chr(10) + 'lines')!r}")

print("\n" + "=" * 76)
print("2. WHY YOU SEND [DONE]")
print("=" * 76)
print(f"  {sse_done()!r}")
print("""  Browsers AUTO-RECONNECT when an SSE stream simply closes. Without a
  sentinel the client reconnects, your server runs the whole agent again, and
  the user watches the answer restart. You pay twice and it looks like a bug in
  the model.""")

print("\n" + "=" * 76)
print("3. FAILING MID-STREAM")
print("=" * 76)
partial = sse({"text": "The deploy failed because"}, event="delta") + sse_error(
    "provider timeout")
for frame in parse_stream(partial):
    print(f"  {frame}")
print("""  You cannot change the HTTP status after the first byte — the 200 already
  shipped. So the error travels INSIDE the stream, and the client has to handle
  that event. If it does not, a mid-stream failure is indistinguishable from a
  short answer. That is the bug behind every "it just stopped" report.""")

print("\n" + "=" * 76)
print("4. DURABILITY — what a crash costs, and what fixes it")
print("=" * 76)

store = RunStore(tempfile.mktemp(suffix=".db"))


def handler(run):
    time.sleep(0.05)
    run.output = f"finished: {run.task}"
    run.cost = 0.02


queue = JobQueue(handler, store, workers=2)
queue.start()
good_run = queue.submit("a task that completes")
time.sleep(0.3)
queue.stop()

# simulate a worker that was OOM-killed halfway through
crashed = store.create("a task whose worker died")
crashed.status = RunStatus.RUNNING
crashed.cost = 0.31          # the money was already spent
store.save(crashed)
conn = store._connect()
with conn:
    conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?",
                 (time.time() - 3600, crashed.id))

print("  before recovery:")
for run in store.list():
    print(f"    {run.id[:8]}  {run.status.value:<10} ${run.cost:.2f}  {run.task}")
print("""
    The second row is what a user sees as a spinner that never resolves. The
    work is gone, the money is spent, and nothing in the system knows.""")

reclaimed = store.reclaim_stale(older_than_s=300, max_attempts=3)
print(f"\n  reclaim_stale() requeued {len(reclaimed)} run(s):")
for run in store.list():
    print(f"    {run.id[:8]}  {run.status.value:<10} ${run.cost:.2f}  {run.task}")

# and the poison pill
poison = store.create("a task that kills its worker")
poison.status = RunStatus.RUNNING
poison.attempts = 3
store.save(poison)
with conn:
    conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?",
                 (time.time() - 3600, poison.id))
store.reclaim_stale(older_than_s=300, max_attempts=3)
poisoned = store.get(poison.id)
print(f"\n  after 3 attempts: {poisoned.status.value} — {poisoned.error}")
print("""
  Without that attempt cap, a run that reliably crashes its worker gets
  requeued forever and takes out every worker in turn. The symptom is
  "throughput is slowly dropping", the cause is one bad input, and the two look
  nothing alike from a dashboard.""")
