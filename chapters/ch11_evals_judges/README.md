# Chapter 11 — Evals II: Judges, Trajectories & Statistics

**Time: ~6 hours** (50 min reading · 30 min examples · 3.5 hrs exercises · 1 hr review)
**Prerequisite:** Chapter 10 green.

---

## After this chapter you can

- Grade free-form output with a model, and know how much to trust the grade
- Control for position bias in pairwise comparison — and explain why you must
- Score *trajectories*, not just answers
- Tell a real improvement from noise, and churn from progress
- Wire a regression gate into CI that people won't learn to ignore

---

## 1. The one idea

Chapter 10 answers "does the output contain 'Paris'?". Some questions have no
assertable answer:

- Is this summary good?
- Is this explanation clear?
- Is answer A better than answer B?
- Did the agent take a *sensible route* to the right answer?

For those you need a judge. And the moment you have a judge, you need statistics —
because a judge produces numbers, and numbers invite conclusions you haven't earned.

## 2. LLM-as-judge

A model grades output against a rubric.

### It works better than people expect, with caveats

Judge/human agreement on a clear rubric is typically 80–90% — around the level of two
humans agreeing with each other. That is good enough to *steer* development. It is not
good enough to be the last word on anything that matters.

### The rubric is the whole thing

```
BAD   "Rate the quality of this summary from 1 to 5."

GOOD  "Score 1-5:
       5 = every fact is in the source, no fact invented, under 100 words
       4 = as above but slightly over length or slightly awkward
       3 = mostly accurate, one minor unsupported detail
       2 = a significant unsupported claim, or badly over length
       1 = contradicts the source"
```

The first produces a number that means nothing and drifts between runs. The second is
nearly deterministic. **Anchor every point on the scale to something observable.**

Three more rules:

- **Ask for reasoning before the score**, in that order in the JSON. It's
  chain-of-thought, and it measurably improves consistency.
- **Give a reference answer when you have one.** Grading against a known-good answer
  is far more reliable than grading in a vacuum.
- **Use a different model from the one being graded**, where you can. Models favour
  their own output — the effect is real and it flatters exactly the thing you are
  trying to measure.

### Judges fail CLOSED

Opposite of Chapter 7's critic, and for a sharp reason:

```python
if unparseable:
    return Judgement(score=self.low, passed=False)   # fail closed
```

A critic that fails open costs you one skipped review. A **judge** that fails open
silently inflates your eval scores — and you will make decisions on those numbers for
months without knowing they're wrong. Grading failures must be visible.

### What a judge cannot do

- **Catch what it doesn't know.** A judge without the source can't detect a
  hallucination.
- **Beat its own ceiling.** A weak judge grading a strong model mostly measures the
  judge.
- **Be a number you report to anyone.** "Our agent scores 4.2/5" is meaningless
  outside your own rubric. Use judges for *deltas*, not for absolutes.

## 3. Pairwise comparison

Models are much better at "which is better?" than "score this 1–5". Relative
judgement is easier than absolute — for models and for people.

### Position bias is real, and large

**Models prefer whichever answer they see first.** (Some prefer the second; it varies
by model.) The effect is big enough to reverse a genuine quality difference.

So judge twice, in both orders:

```
A vs B → "A"        B vs A → "A" (= original B)     DISAGREE → tie
A vs B → "A"        B vs A → "B" (= original A)     AGREE    → A wins
```

Two calls instead of one. **Pay it.** A pairwise eval without position control is
measuring the judge's layout preference, not your agent.

A useful side effect: the disagreement rate *is* your noise floor. If the two orders
disagree 40% of the time, your rubric isn't discriminating, and no amount of sample
size will fix that.

## 4. Trajectory evaluation

The right answer reached the wrong way is a bug that ships. Three strictness levels:

| Check | Meaning | Use when |
|---|---|---|
| `trajectory_exact` | identical sequence | rarely — most tasks have several valid orders |
| `trajectory_contains` | these tools, in this order, gaps allowed | **almost always this one** |
| `trajectory_similarity` | 1 − editdistance/maxlen, graded | when you want a trend, not a gate |

`trajectory_contains(["search", "read_file"])` says "it looked something up before
answering". Whether it also listed a directory first is not your business.

The graded version matters more than it sounds: "one tool off" and "completely
different plan" are very different failures, and a boolean throws that distinction
away. When you are trying to see whether a change helped, you want the gradient.

## 5. Statistics, or how not to fool yourself

### Your sample is smaller than you think

50 cases, 42 passed. 84%. The 95% confidence interval is roughly **72%–92%**.

So an "improvement" from 84% to 88% on 50 cases is **inside the noise**. People ship
changes on differences like that every day and revert them a month later having
learned nothing.

```python
low, high = bootstrap_ci(42, 50)     # (0.72, 0.92)
```

Bootstrap: resample your results with replacement a few thousand times, take the 2.5th
and 97.5th percentiles of the resampled rates. Twelve lines, no dependencies, and it
will stop you making bad calls.

**Rough guide:** to detect a 5-point difference reliably you want ~400 cases. To detect
a 15-point difference, ~50 is fine. Know which kind of change you're measuring.

### Compare case by case, not by headline

This is the most useful thing in the chapter:

```
baseline  42/50   candidate  42/50     "no change"
```

Except six cases broke and six others got fixed. That is not stability, that is an
**unstable agent** — and the headline rate hid it completely.

```python
result = compare_runs(baseline, candidate)
result.improved     # ['case-12', 'case-31', ...]
result.regressed    # ['case-04', 'case-19', ...]
```

Always read `regressed`. A change that fixes eight and breaks three might still be
right — but you should *know*, and you should look at the three.

### The significance rule here is crude on purpose

`compare_runs` calls a difference significant when the two flip counts differ by at
least 5. That is a stand-in for McNemar's test. It is not rigorous; it is *present*,
which beats the usual alternative of eyeballing two percentages. If you need the real
test, `scipy.stats` has it.

### Temperature and reproducibility

Run evals at `temperature=0` for comparability. Even then results move slightly —
batching and floating-point non-associativity on GPU mean inference isn't bit-exact
(Track C explains exactly why). For anything you're going to act on, **run the suite
3× and look at the spread** before you trust a difference.

## 6. Putting it in CI

```yaml
- run: python -m evals.run --suite smoke      # 10 cases, every commit
- run: python -m evals.run --suite full       # 200 cases, nightly
```

- Gate on the **smoke** suite. Fast, cheap, catches the obvious.
- Run the **full** suite nightly and on release branches.
- **Store every report.** A history of pass rates is how you notice slow drift, which
  is the failure mode nobody catches in the moment.
- **Set the gate at your current score minus the noise**, then ratchet. A gate that is
  always red is a gate everyone disables.

## 6b. After CI: evals in production

A golden set measures the cases you thought of. Real users will send ones you didn't.
Once you ship, you need a second loop that runs on live traffic.

```
  live traffic ──► traces (ch12) ──► sample ──► judge + signals ──► dashboard
       ▲                                                 │
       └──── fix ◄── new golden cases ◄── triage worst ◄─┘
```

**Online evals.** Run your Chapter 11 judge on a **sample** of real traces, say 1–5%,
asynchronously and never in the request path. You get a quality number for real
traffic, not only for your dataset. Use a cheap judge model and cap the daily spend.

**User signals are free labels, though noisy:**

| Signal | Kind | What it suggests |
|---|---|---|
| Thumbs up/down | explicit | Direct, but only ~1% of users click, and mostly angry ones |
| User retries or rephrases | implicit | The first answer missed |
| User edits the agent's output | implicit | Close, but wrong. The diff is gold. |
| User abandons mid-task | implicit | Lost them |
| Escalation to a human | implicit | The agent gave up or should have |

**Rolling out a change** (new prompt, new model, new tool), from safest to fastest:

1. **Offline evals.** The CI gate above. Always first.
2. **Shadow mode.** Run the new version alongside the old one on real inputs, show
   users only the old output, and compare the two offline with a pairwise judge (§3).
   You get real inputs with zero user risk, at double the cost.
3. **Canary.** Send 1–5% of traffic to the new version and watch online scores,
   errors, cost and latency. Roll back automatically if they cross a threshold.
4. **A/B test.** Split traffic in half and compare user signals. Because the signals
   are noisy you need lots of traffic, so mostly only large products can do this.

**Close the loop.** Every week, take the worst-scored live traces, work out what went
wrong, and add them to the golden set together with a negative sibling (Chapter 10).
This is how the dataset keeps up with how the product is actually used.

**Privacy.** Live traces contain user data. Redact before judging (Chapter 9's
`RedactPII`), and check what your users agreed to before you send their conversations
to a third-party judge model.

## 7. Common mistakes

1. **A vague rubric.** Numbers that drift and mean nothing.
2. **Score before reasoning.** You threw away the chain-of-thought.
3. **Judging with the model being graded.** It flatters itself.
4. **A judge that fails open.** Silently inflated scores for months.
5. **Reporting "4.2/5" as if it were meaningful.** It isn't, outside your rubric.
6. **Pairwise without position control.** You measured the layout.
7. **`trajectory_exact` everywhere.** Most tasks have several valid orders.
8. **No trajectory checks at all.** Right answer, absurd route, invisible.
9. **Acting on 84% → 88% with n=50.** Noise.
10. **Reading only the headline rate.** Churn looks like stability.
11. **Never looking at `regressed`.** You shipped the fix and the break together.
12. **Evals at temperature > 0.** Now you can't compare anything.
13. **Stopping at offline evals.** The golden set drifts away from real traffic.
14. **Shipping a prompt or model change straight to 100%.** Use shadow or canary first.

## 8. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_judge.py` | `LLMJudge`, `Judgement`, fail-closed parsing, `as_check` |
| 2 | `exercise_2_pairwise.py` | `pairwise_compare` with position-bias control |
| 3 | `exercise_3_trajectory.py` | `is_subsequence`, `levenshtein`, the three trajectory checks |
| 4 | `exercise_4_stats.py` | `bootstrap_ci`, `compare_runs` |
| 5 | `exercise_5_regression.py` | **Integration:** a real regression suite with a CI gate |

```bash
pytest chapters/ch11_evals_judges/tests -q
```

## 9. Check yourself

1. What can a judge answer that an assertion cannot?
2. Rewrite "rate this 1–5" as a rubric that would actually be consistent.
3. Why reasoning *before* score?
4. Why not judge with the model under test?
5. Why do judges fail closed when critics fail open?
6. Describe position bias and the two-call fix. What does the disagreement rate tell you?
7. Which trajectory check should be your default, and why not the strict one?
8. 42/50 vs 44/50. Is that an improvement?
9. Both runs score 42/50 but six cases flipped each way. What have you learned?
10. Roughly how many cases to detect a 5-point difference?
11. Why run evals at temperature 0, and why is that still not fully reproducible?
12. Where do you set a CI gate, and what happens if you set it aspirationally?
13. Name three implicit user signals and what each one suggests.
14. Shadow mode vs canary: what risk does each remove, and what does each cost?

---

**Next:** Chapter 12 — when an eval fails, you need to see inside the run. Tracing.
