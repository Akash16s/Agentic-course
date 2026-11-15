# Chapter 7 — Planning & Reflection

**Time: ~6 hours** (45 min reading · 35 min examples · 3.5 hrs exercises · 1 hr review)
**Prerequisite:** Chapters 1–6 green.

---

## After this chapter you can

- Say when planning beats reacting, and when it is just expensive ceremony
- Build a plan with dependencies, run independent steps in parallel, and handle
  failures without deadlocking
- Parse model-generated plans robustly, including the cycles and dangling references
  models actually produce
- Implement reflection, and — more importantly — tell whether it is helping

---

## 1. The one idea

Chapter 3's loop is **reactive**: it sees the last observation and picks one action.
That's fine for three steps and starts to wander at fifteen.

Two augmentations, both cheap to describe and easy to overuse:

**Plan-and-execute** — decide the steps first, then run them.
**Reflection** — check your own work, and revise.

The honest framing: both trade tokens and latency for reliability on *some* tasks and
buy you nothing on others. This chapter is as much about telling the difference as
about the implementation.

## 2. Plan-and-execute

```
                 ┌──────────────┐
      goal ─────►│   PLANNER    │──► [step 1, step 2, step 3 (after 1,2)]
                 └──────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   EXECUTOR   │ ready steps → run (parallel if independent)
                 │              │ ──► results back into the plan
                 └──────┬───────┘
                        │ blocked or failed?
                        ▼
                 ┌──────────────┐
                 │   REPLAN     │ (at most once or twice)
                 └──────────────┘
```

### Why bother

- **The plan is visible.** You can show it to a user, log it, diff it against what
  actually happened. A reactive agent's intent is only ever implicit.
- **Independent steps run in parallel.** A reactive loop is inherently serial: it
  cannot start step 2 until it has seen step 1's result, even when it doesn't need it.
- **It resists wandering.** The plan is a commitment. The rambler pathology from
  Chapter 3 largely disappears.
- **It is resumable.** A plan is serialisable state; a half-finished loop is not.
  (Chapter 15 cares a lot about this.)

### Why not

- **A plan made before you know anything is often wrong.** For genuinely exploratory
  work the first two steps invalidate the last three.
- **It costs an extra call and adds latency** before any work starts.
- **Plans deadlock** in ways a simple loop cannot. That is most of the engineering
  below.

**Rule of thumb:** plan when the steps are knowable in advance and some are
independent. React when each step depends on the last. Many real agents do both — a
plan at the top, a reactive loop inside each step.

### Dependencies are the whole design

`depends_on` is what makes a plan more than a list:

```json
[{"id": 1, "description": "read config/database.yml",     "depends_on": []},
 {"id": 2, "description": "read config/redis.yml",        "depends_on": []},
 {"id": 3, "description": "compare the timeout settings", "depends_on": [1, 2]}]
```

Steps 1 and 2 have no dependency on each other, so they run **together**. Step 3 waits.

Two rules that follow:

- **`ready_steps()` returns a list, not a step.** Everything in it runs concurrently.
- **Unnecessary dependencies cost you wall-clock.** Tell the planner so explicitly;
  models over-serialise by default because a numbered list feels sequential.

### Four ways a plan deadlocks

This is where the real work is. All four happen with real models.

| Failure | What it looks like | Fix |
|---|---|---|
| **Dangling dependency** | Step 3 depends on step 9, which doesn't exist. Nothing is ever ready. | Drop unknown ids at parse time |
| **Cycle** | 1 → 2 → 1. Nothing is ever ready. | Remove back-edges at parse time |
| **Blocked by failure** | Step 1 failed; step 3 waits for it forever | `skip_blocked()` — cascade the failure |
| **Self-dependency** | Step 2 depends on step 2 | Drop it at parse time |

All of these present as a **hang**, not an error. The executor loops, finds nothing
ready, and spins until its round budget runs out. Repairing the plan at parse time is
much cheaper than diagnosing it at runtime.

### Re-planning

When a step fails or the plan turns out to be wrong, re-plan with what you now know:

```python
PlanExecutor(run_step, replan=make_new_plan, max_replans=1)
```

**Cap it hard — one or two.** Unlimited re-planning is how an agent spends $40
enthusiastically achieving nothing. If two plans in a row fail, the problem is not the
plan.

## 3. Reflection

Produce → critique → revise:

```python
answer = produce(None)
for _ in range(max_rounds):
    critique = criticise(task, answer)
    if critique.acceptable:
        break
    answer = produce(critique.suggestion)
```

### When it genuinely helps

**When the critic can check something the producer didn't.** That is the entire test.

- Code that must compile — run it, feed the errors back. This works extremely well.
- Output that must match a schema — validate it. Works.
- Claims that must be supported by retrieved sources — check each one. Works.
- A task with an explicit checklist — verify each item. Works.

### When it is theatre

**When the critic has exactly the same information as the producer.** Then you are
asking a model to find fault in its own output with no new evidence, and it will
comply, because you asked. You get a differently-worded answer for 2–3× the cost.

Matters of taste are the clearest example: "is this explanation clear?" has no ground
truth, and the critic's objections are generated rather than found.

**The one rule:** give the critic something the producer lacked — a compiler, a
schema, the sources, a checklist, a different model. Otherwise measure it (Chapter 10)
before shipping it, and be prepared to find it does nothing.

### Failing open

If the critic's output can't be parsed, treat it as **acceptable**:

```python
def parse_critique(raw) -> Critique:
    obj = _json_object(raw)
    if obj is None:
        return Critique(acceptable=True)   # fail open
```

Fail closed and one malformed response sends the agent into an endless revision loop —
expensive, and invisible because every round looks like progress. Failing open costs
you one missed review.

## 4. Chain-of-thought, briefly

"Think step by step" is the smallest version of all this. Worth knowing where it now
stands:

- **Reasoning models do it internally.** With o-series, Claude's extended thinking and
  similar, telling them to think step by step is redundant and sometimes harmful.
- **For non-reasoning models it still helps** on multi-step arithmetic and logic.
- **It costs output tokens**, which are the expensive ones *and* the slow ones
  (Chapter 1, §5).
- **Thinking is not doing.** An agent that reasons beautifully and then calls the
  wrong tool has not been helped. Judge by the trajectory, not the prose.

## 5. Common mistakes

1. **Planning a task where each step depends on the last.** Pure overhead.
2. **Not repairing plans at parse time.** Cycles and dangling ids present as hangs.
3. **No `skip_blocked`.** One failed step stalls the executor silently.
4. **Unlimited re-planning.** The most expensive way to achieve nothing.
5. **`ready_steps()` returning one step.** You threw away the parallelism.
6. **Over-serialised plans.** Tell the planner that independent steps run in parallel.
7. **A critic with no extra information.** Theatre, at 2–3× the price.
8. **Failing closed on an unparseable critique.** Endless revision.
9. **Assuming reflection helps.** Measure it. Sometimes it makes things worse.
10. **Planning steps for reporting the answer.** The loop already does that.

## 6. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_plan.py` | `Plan`, `PlanStep`, `ready_steps`, `skip_blocked`, `render` |
| 2 | `exercise_2_parse.py` | `parse_plan` — robust against everything models emit |
| 3 | `exercise_3_executor.py` | `PlanExecutor` — parallel-ready, failure-tolerant, re-planning |
| 4 | `exercise_4_reflection.py` | `Critique`, `parse_critique`, `reflect_loop` |
| 5 | `exercise_5_planning_agent.py` | **Integration:** plan-and-execute over real tools |

```bash
pytest chapters/ch07_planning/tests -q
```

## 7. Check yourself

1. When does planning beat reacting? Give a task for each.
2. Why does `ready_steps()` return a list?
3. Name the four ways a plan deadlocks. What do they all look like from outside?
4. Why repair the plan at parse time rather than detecting problems at runtime?
5. What does `skip_blocked` cascade, and what happens without it?
6. Why cap re-planning at one or two?
7. What single property decides whether reflection is useful?
8. Give a reflection setup that works and one that is theatre.
9. Why does `parse_critique` fail open?
10. When is "think step by step" redundant or harmful?

---

**Next:** Chapter 8 — more than one agent, and the honest case against it.
