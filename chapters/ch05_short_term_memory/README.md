# Chapter 5 — Short-Term Memory

**Time: ~5 hours** (40 min reading · 30 min examples · 3 hrs exercises · 50 min review)
**Prerequisite:** Chapters 1–4 green.

---

## After this chapter you can

- Separate *storage* (what was said) from *strategy* (what the model sees), and say why
- Persist conversations so they survive a restart and a second worker
- Implement three memory strategies and pick between them for a given product
- Avoid the summarisation cost trap that makes naive memory more expensive than no memory
- Explain what short-term memory cannot do, which is why Chapter 6 exists

---

## 1. The one idea

**Storage and strategy are different jobs. Keep them apart.**

```
        ┌─────────────────┐        ┌──────────────────┐       ┌────────┐
 write  │  SessionStore   │  read  │  MemoryStrategy  │ build │ model  │
───────►│  the full,      ├───────►│  what to SHOW    ├──────►│ sees   │
        │  lossless record│        │  this turn       │       │ this   │
        └─────────────────┘        └──────────────────┘       └────────┘
             durable                   cheap, swappable,
             never lossy                sometimes lossy
```

Almost every memory bug traces back to conflating these. A store that trims can never
give you the full transcript back — so you cannot debug, cannot re-run under a better
strategy, cannot show the user their own history. Keep the record complete; make the
*view* cheap.

## 2. Why Chapter 1's `Conversation` isn't enough

It's a Python object in RAM. That means:

- **It dies with the process.** Deploy, and every user's conversation vanishes.
- **It doesn't exist for the next worker.** Two uvicorn workers = two different
  conversations for the same user, alternating at random. This bug is maddening because
  it works perfectly on your laptop with one process.
- **It has no identity.** Real systems have many users with many threads each.
- **It grows without bound.** Chapter 4 gave you the tools; nothing is applying them.

## 3. The store interface

```python
class SessionStore(ABC):
    def load(self, session_id) -> Session
    def save(self, session) -> None
    def delete(self, session_id) -> None
    def list_sessions(self) -> list[str]
```

Four methods. Resist adding more.

Notice what is **not** here: no `trim`, no `summarise`, no `count_tokens`. A store that
does those things is a store you cannot swap, and swapping it is the entire reason the
interface exists. In-memory for tests, SQLite for a single box, Redis or Postgres when
you have several.

**`load` of an unknown id returns an empty `Session`, not `None`.** Every caller would
otherwise write the same three lines of None-handling, and one of them would forget.

**`load` returns a copy.** If it hands back the stored object, a caller that mutates it
has silently written to your store without saving. That bug looks like "sometimes the
history has messages we never persisted".

### SQLite: the default you should reach for

Not a toy. One file, no server, ACID transactions, and it handles more concurrent
readers than most people's actual traffic.

Two details that matter:

**Store messages as one JSON blob, not one row per message.** We always read and write
a whole conversation, never a single message. A blob is one query; rows are N plus a
join. Normalise when you need to query *inside* conversations — which is Chapter 6's
problem, not this one.

**One connection per thread.** `sqlite3` connections are not thread-safe. Use
`threading.local()`. Sharing one connection across a thread pool produces
`ProgrammingError: SQLite objects created in a thread can only be used in that same
thread`, usually under load, usually in production.

## 4. Three strategies

### FullHistory — send everything

Correct, and correct is worth something. Fine for short-lived tasks and anything where
the conversation is bounded by construction.

Fails silently: it works, works, works, and then a user has a long day.

### SlidingWindow — keep the ends

Chapter 4's `trim_messages` behind the strategy interface. `keep_first` protects the
task statement, `keep_last` protects current state, the middle goes.

Good for: chat, support, anything where old turns genuinely stop mattering.
Bad for: research or coding agents, where turn 3 established a fact you need at turn 40.

### SummaryBuffer — compact and cache

Old turns become a summary; recent turns stay verbatim. The best default for long
conversations, *if you get two details right*.

**Detail one: cache the summary.** The naive version summarises on every turn:

```
turn 10: summarise 9 turns    $0.002
turn 11: summarise 10 turns   $0.002
turn 12: summarise 11 turns   $0.003
...
```

That is a second quadratic, on top of the one from Chapter 1. You can easily spend more
on summarising a conversation than on having it. Instead: summarise once past a
threshold, cache the result, and only re-summarise when the *new* messages since the
last summary grow past the threshold again.

**Detail two: carry the old summary forward.** When you re-summarise, feed the previous
summary in as context:

```
PREVIOUS SUMMARY:
<the old one>

CONVERSATION SINCE:
<new turns>
```

Without this, facts from the first hour get dropped the second time you compact. With
it, they survive — a little more lossily each round, which is honest.

### Picking one

| Situation | Strategy |
|---|---|
| Short task, bounded turns | FullHistory |
| Chat / support, old turns irrelevant | SlidingWindow |
| Long session where early facts matter | SummaryBuffer |
| Facts must survive across *different* sessions | **Chapter 6** — this is not it |

## 5. What short-term memory cannot do

It is scoped to one conversation. It cannot:

- recall what the user told you last week in a different thread
- share knowledge between two agents
- search semantically ("what did we decide about pricing?")
- forget selectively — it forgets by age, not by relevance

Those are long-term memory, and they need embeddings and a vector store. Chapter 6.

The distinction people blur: **short-term memory is about a conversation; long-term
memory is about a user.** A summary of today's chat is short-term. "This user prefers
Python and works in fintech" is long-term, and belongs somewhere a new conversation can
find it.

## 6. Locking, concurrency and the lost update

Two requests for the same session at once:

```
request A: load (5 messages) ──┐
request B: load (5 messages) ──┤
request A: append, save (6) ───┤
request B: append, save (6) ───┘   A's message is gone
```

Classic lost update. Options, in increasing order of effort:

- **Append-only writes.** Don't read-modify-write the whole blob; `INSERT` the new
  messages. Requires the row-per-message schema you avoided above — a real trade.
- **A per-session lock.** Easy in one process, needs Redis or similar across many.
- **Optimistic concurrency.** Store a version, fail the save if it changed, retry.
- **Serialise by session.** Route all requests for a session to one worker, or one
  queue. Chapter 15.

For this chapter a `threading.Lock` in the in-memory store is enough, and knowing the
problem exists is the point.

## 7. Common mistakes

1. **A store that trims.** Now the record is lossy and you cannot debug anything.
2. **`load` returning the stored object.** Callers mutate it; writes appear from nowhere.
3. **`load` returning `None`.** Every caller reimplements the same guard.
4. **Summarising on every turn.** More expensive than the conversation itself.
5. **Not carrying the previous summary forward.** Early facts silently vanish.
6. **One SQLite connection shared across threads.** Fails under load only.
7. **Session state in a module-level dict with >1 worker.** Works locally, alternates
   in production.
8. **No `session_id` in your logs.** Debugging a multi-user agent without it is hopeless.
9. **Reaching for short-term memory when the need is cross-session.** Wrong chapter.

## 8. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_store.py` | `Session`, `SessionStore`, `InMemorySessionStore` |
| 2 | `exercise_2_sqlite.py` | `SQLiteSessionStore` — durable, thread-safe |
| 3 | `exercise_3_strategies.py` | `FullHistory`, `SlidingWindow` |
| 4 | `exercise_4_summary.py` | `SummaryBuffer` — with the cache and the carry-forward |
| 5 | `exercise_5_service.py` | **Integration:** a multi-session stateful chat (needs your key) |

```bash
pytest chapters/ch05_short_term_memory/tests -q
```

## 9. Check yourself

1. Storage vs strategy: what does each own, and what breaks if you merge them?
2. Three things that go wrong with an in-RAM `Conversation` in production.
3. Why does `load` return an empty `Session` rather than `None`?
4. Why does `load` return a copy?
5. Why one JSON blob per session rather than one row per message? When would you flip?
6. What error do you get from sharing a SQLite connection across threads, and when?
7. Describe the summarisation cost trap and the two fixes.
8. What happens to facts from the first hour if you don't carry the summary forward?
9. Sketch the lost-update race and name two mitigations.
10. "The user told me last week they work in fintech." Short-term or long-term? Why?

---

**Next:** Chapter 6 — embeddings, a vector store built from scratch, and memory that
crosses conversations.
