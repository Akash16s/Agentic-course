# Chapter 10 — Evals I: The Harness

**Prerequisite:** Chapters 1–9 green.

---

## After this chapter you can

- Explain why an agent without evals cannot be improved on purpose
- Build a golden dataset that is small, hard, and actually reveals problems
- Write assertion checks for output *and* for trajectory
- Run an eval suite in parallel, offline, for free
- Read a report and know what to fix next — not just that something is wrong

---

## 1. The one idea

**Without evals, every change is a guess.**

Here is the loop everyone runs without evals:

```
tweak the prompt → try 3 examples by hand → "seems better" → ship
                → a week later something else is broken → tweak again
```

You cannot tell improvement from regression. You cannot tell whether the expensive
model is worth it. You cannot refactor. You cannot change models when prices move.
And crucially: **you cannot tell whether the last five things you added helped.**

Here is the loop with evals:

```
change → run 50 cases → 84% → 89% → keep it
                             → 71% → revert, and look at which check broke
```

This chapter is the mechanics. Chapter 11 is the hard cases — grading things that
have no single right answer.

**The best time to build this was Chapter 3.** It is here because you needed
something worth evaluating first, but in a real project the harness comes early —
while the dataset is ten cases you wrote in an afternoon, not two hundred you have
to reconstruct.

## 2. The golden dataset

A set of inputs with known-good outcomes. Almost everything about eval quality is
dataset quality.

### Small and hard beats big and easy

**30–50 well-chosen cases beat 500 random ones.** A suite of easy cases sits at 98%
forever and tells you nothing; every change looks neutral. You want cases that
*discriminate* — where a worse agent scores visibly lower.

### Where cases come from, best first

1. **Real failures.** Every time the agent gets something wrong in development or
   production, that input becomes a case. This is by far the highest-value source,
   and it is free.
2. **Real usage.** Sample actual traffic, even if you have to label it by hand.
3. **Edge cases you reason about.** Empty input, hostile input, ambiguous input,
   another language, something the agent should *refuse*.
4. **Synthetic, from a model.** Cheap, plentiful, and systematically easier than
   reality. Useful for volume; never let it be your whole suite.

### Every case needs a negative sibling

For every "the agent should do X", have a case where it should **not**:

```jsonl
{"id": "refund-01", "input": "I want a refund",         "expected": "refund_policy", "tags": ["refund"]}
{"id": "refund-02", "input": "What's your refund rate?", "expected": "not_a_refund_request", "tags": ["negative"]}
```

Without negatives, an agent that calls `process_refund` on everything scores 100%.

### JSONL, not JSON

Append a case without rewriting the file. Diff it line by line in review. Eval
datasets are hand-edited constantly, and that decides the format.

## 3. Checks

A check takes `(output, case)` and returns pass/fail with a reason. Two families:

### Output checks — what it said

`contains` · `not_contains` · `matches` (regex) · `equals_expected` ·
`expected_contains`

**Normalise before comparing.** Without `.strip().lower()`, a third of your failures
are whitespace and you stop trusting the suite — which is worse than having no suite,
because you now ignore real failures too.

### Trajectory checks — what it did

This is where `AgentResult` (Chapter 3) pays for itself:

`tool_called` · `tool_not_called` · `max_steps` · `max_cost` · `succeeded`

**These catch things output checks cannot.** An agent that reaches the right answer
by calling `search` eleven times is broken, and its output looks perfect. An agent
that answers from memory instead of using the tool you gave it is *also* broken, and
today it happens to be right.

`tool_not_called` is the one people skip and the one that catches real damage —
`tool_not_called("delete_user")` on every case in the suite costs nothing and is
exactly the check you will wish you had.

### Checks must never raise

A check that throws should record a failure, not take down the run. Same for a case
that errors: one crashing case must not cost you the other 199 results.

## 4. The report

Three numbers and one table:

```
support-v3: 42/50 passed (84%)  $0.31  18.4s  p50 0.32s
  failures by check: tool_called x6, max_steps x3, expected_contains x2
```

**`failures_by_check` is the most actionable line in the report.** A pass rate tells
you something is wrong. This tells you *what*: six cases didn't call the tool at all,
which is a tool-description problem, not a prompt problem.

Also track **cost** and **p50 duration**. A change that lifts accuracy 2% and triples
cost is usually a bad trade, and you will not notice unless the report says so.

## 5. Thresholds and gates

```python
report = runner.run(dataset)
if not report.meets(0.85):
    sys.exit(1)          # fails the build
```

**Set the threshold from your current score, not from an aspiration.** If you are at
84%, gate at 82%. A gate at 95% that always fails is a gate everyone learns to
ignore, and then it protects nothing.

Ratchet it up as you improve. That is the whole mechanism: the gate stops you going
backwards, it does not drag you forwards.

## 6. Running cheaply

- **Parallelise.** Cases are independent. 50 cases at 4-way concurrency is 12×
  faster, and rate limits are the only real constraint.
- **Use a cheap model for iteration**, your real model before you ship.
- **Cache** (Chapter 13). Re-running the same suite against an unchanged agent
  should cost nothing.
- **Tier your suites.** A 10-case smoke suite on every commit; the full 200 nightly.
- **Keep the harness testable offline.** All the tests in this chapter run against
  fakes for $0, and yours should too.

## 7. What this chapter cannot do

Assertions only work when there is something to assert. They cannot tell you whether
a summary is *good*, whether an explanation is *clear*, or whether an answer is
*better* than another answer.

That is Chapter 11: LLM-as-judge, rubrics, pairwise comparison, and the statistics
you need to not fool yourself.

## 8. Common mistakes

1. **No evals.** Every change is a guess.
2. **Easy cases.** 98% forever, zero signal.
3. **500 synthetic cases and no real failures.** Volume is not coverage.
4. **No negative cases.** An agent that always acts scores 100%.
5. **Output checks only.** Right answer, eleven tool calls, invisible.
6. **No `tool_not_called` for destructive tools.** Free to add, expensive to omit.
7. **Comparing without normalising.** Whitespace failures, then ignored failures.
8. **A check that raises kills the run.**
9. **A case that errors kills the run.**
10. **Not tracking cost.** +2% accuracy, 3× the bill, shipped by accident.
11. **An aspirational gate.** Always red, universally ignored.
12. **Running serially.** 50 sequential agent runs is a coffee break per change.

## 9. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_dataset.py` | `EvalCase`, `Dataset`, JSONL round trip, filtering |
| 2 | `exercise_2_checks.py` | The output and trajectory checks |
| 3 | `exercise_3_results.py` | `CaseResult`, `EvalReport`, `failures_by_check`, gates |
| 4 | `exercise_4_runner.py` | `EvalRunner` — parallel, error-tolerant |
| 5 | `exercise_5_real_eval.py` | **Integration:** evaluate your Chapter 3 agent for real |

```bash
pytest chapters/ch10_evals_basics/tests -q
```

## 10. Check yourself

1. What can you not do without evals? Name three things.
2. Why do 30 hard cases beat 500 easy ones?
3. Rank the four sources of eval cases. Why is #1 first?
4. What does a negative case protect against?
5. Why JSONL?
6. Give a failure an output check misses and a trajectory check catches.
7. Which check would you add to every case in a suite with a destructive tool?
8. Why must a failing check not raise?
9. Which line of the report tells you what to fix, and why isn't it the pass rate?
10. Where should you set a gate threshold, and what happens if you aim high?
11. Two ways to make a suite cheap enough to run on every commit.
12. What kind of question can an assertion suite not answer at all?

---

**Next:** Chapter 11 — grading the things you cannot assert on, without fooling
yourself.
