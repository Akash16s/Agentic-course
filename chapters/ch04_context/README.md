# Chapter 4 — Context Engineering

**Time: ~5 hours** (45 min reading · 30 min examples · 3 hrs exercises · 45 min review)
**Prerequisite:** Chapters 1–3 green.

---

## After this chapter you can

- Budget a context window deliberately instead of hoping
- Explain why cutting a conversation in the wrong place returns a 400, and cut correctly
- Truncate tool output without throwing away the part that matters
- Compact a long conversation into a summary that lets another model continue it
- Structure a system prompt so the least important part is what gets dropped

---

## 1. The one idea

**The context window is a budget, and every token in it is competing for the model's
attention.** Context engineering is deciding, deliberately, what earns a place.

Your loop from Chapter 3 works. It also grows monotonically: every step adds an
assistant message and one or more tool results, forever, until the window bursts. A
20-step agent reading files can hit 100k tokens without doing anything unusual.

Three separate problems, often confused:

| Problem | Symptom | Chapter |
|---|---|---|
| **Overflow** | 400 "context length exceeded", run dies | this one |
| **Cost** | Quadratic growth, big bills | this one + 13 |
| **Attention** | Everything fits, answers get *worse* | this one |

The third is the one people miss. Filling a 200k window does not make the model smarter.

## 2. What's actually in your window

```
┌─────────────────────────────────────────────────────────┐
│ SYSTEM PROMPT           fixed, every call    ~200-2,000 │
├─────────────────────────────────────────────────────────┤
│ TOOL SCHEMAS            fixed, every call    ~100/tool  │
├─────────────────────────────────────────────────────────┤
│ CONVERSATION HISTORY    grows every step     unbounded  │
│   user / assistant / tool_calls / tool results          │
├─────────────────────────────────────────────────────────┤
│ RESERVE FOR OUTPUT      must be left free    ~1-8k      │
└─────────────────────────────────────────────────────────┘
                          ↑
                   all of this shares ONE window
```

That last row is the one people forget. **The window is shared between input and
output.** A 128k model with a 126k prompt has 2k left to answer in, and you will get a
truncated reply with `finish_reason: "length"` and no idea why.

```python
available_for_history = context_window - system - tools - reserve_output
```

Compute it. Do not guess it.

## 3. Attention is not uniform

Two findings that should change how you lay out a prompt:

**Lost in the middle.** Models attend most strongly to the *beginning* and the *end* of
their context, and weakest to the middle. Bury a critical instruction at 50% depth in a
long context and it gets missed.

Practical consequences:
- Put standing rules in the **system prompt** (the start).
- Put the immediate task in the **last user message** (the end).
- Put bulk retrieved material in the **middle**, where dilution costs least.
- If one instruction absolutely must be followed, it is fine to state it twice — top and
  bottom. It looks redundant. It works.

**Context rot.** As a context fills with tool output, old reasoning and dead ends, answer
quality degrades even well below the limit. The model is distracted by its own history.
A long conversation is not just expensive, it is *worse*, which is why compaction is a
quality technique and not only a cost one.

## 4. Grouping: the bug that only appears in production

You cannot trim a message list by slicing it. Look at what the loop produces:

```
user            "compare a.txt and b.txt"
assistant       content=None, tool_calls=[c1: read(a.txt), c2: read(b.txt)]
tool  (c1)      "contents of a..."
tool  (c2)      "contents of b..."
assistant       "a is longer."
```

Messages 2, 3 and 4 are **one atomic unit**. Cut between them and you send the model a
`role: tool` message answering a `tool_call_id` that appears nowhere in the conversation.
Every provider rejects that with a 400:

```
messages: tool_call_id 'c1' not found in preceding assistant message
```

The reverse is just as bad: an assistant message with `tool_calls` and no results
following it. The model sees a question it asked and no answer.

So: **group first, then trim whole groups.**

```python
def message_pairs(messages) -> list[list[Message]]:
    # [user] [assistant+tool_calls, tool, tool] [assistant] ...
```

This is `message_pairs` in Exercise 2, and it is the most load-bearing 15 lines in the
chapter. The bug it prevents is invisible in development — short conversations never
trim — and appears the day a user has a long session.

## 5. Four strategies, in order of how much they cost you

### 1. Truncate tool output (cheap, do it always)

One `read_file` on a 2MB log can eat your whole window in a single step. Cap every tool
result at the boundary.

**Cut the middle, not the tail.** For a stack trace, a diff or a JSON response, the
start says what it is and the end says what went wrong. Plain truncation keeps the least
useful part:

```python
"ERROR: connection failed\n  at foo()\n  ...[8,412 chars cut]...\n  caused by: DNS timeout"
```

### 2. Sliding window (cheap, lossy, blunt)

Keep the last N groups, drop the rest. Fine for chat. Bad for agents: the task statement
is usually in turn 1, and dropping it means the agent forgets what it was doing.

Mitigation: `keep_first` as well as `keep_last`. Protect the opening turns *and* the
recent ones, and cut from the middle — which is also where attention was weakest anyway.

### 3. Compaction / summarisation (costs a call, keeps the plot)

Replace old groups with a model-written summary:

```
user      [Summary of the earlier conversation]
          The user wants to migrate the billing service from MySQL to Postgres.
          We established: schema is in db/schema.sql, 14 tables, 3 use MySQL-specific
          JSON functions. We tried pgloader and it failed on the `invoices` table
          because of an enum. Outstanding: decide how to map enums.
assistant ...recent turns, verbatim...
```

Rules that make the difference between a useful summary and a useless one:

- **Prompt for specifics.** "Preserve names, ids, paths, numbers, URLs." Generic
  summaries ("the user asked about databases") are worse than useless — they read like
  information while containing none.
- **Preserve what was already tried.** Otherwise the agent re-treads dead ends, which is
  the most common post-compaction failure.
- **Keep the recent turns verbatim.** Summarise the old, never the current state.
- **Use a `user` message**, not `system`. Mid-conversation system messages are ignored by
  some providers and rejected by others.
- **Compact at a threshold, not every turn.** Around 70% of `available_for_history`.

### 4. Externalise (best, needs design)

Don't put it in the window at all. Write findings to a file or a store and give the agent
a tool to read them back. The context holds a *pointer*; the data lives outside. This is
what Chapter 6's long-term memory is, and what a coding agent does when it greps instead
of reading your whole repo.

## 6. Structuring the system prompt

A real system prompt is assembled from parts, not typed as one string:

```python
prompt = (PromptBuilder()
    .add("role",      "You are a support agent for Acme.",  priority=0, required=True)
    .add("rules",     RULES,                                priority=10, required=True)
    .add("date",      f"Today is {today}.",                 priority=20)
    .add("user",      profile_text,                         priority=30)
    .add("memories",  retrieved_memories,                   priority=80)
    .render(max_tokens=budget.system_tokens))
```

Priorities mean that when space runs out, the retrieved memories get dropped and the
rules do not. Without them, something gets dropped anyway — usually by truncating the
middle of a sentence.

**Write rules as positives.** "Answer in three sentences" beats "don't be verbose";
"cite the document id" beats "don't make things up". Models follow instructions about
what to *do* far more reliably than prohibitions.

### Few-shot examples: the strongest instruction you have

One worked example usually does more than a paragraph of rules. Models copy what
they see in the prompt, including its format, length and tone. That copying is what
makes examples powerful, and also what makes them risky:

```python
EXAMPLES = """
<example>
User: refund order 8812
Assistant: [calls lookup_order(order_id="8812")] ... [calls issue_refund(...)]
Refunded $42.10 to the original card. It usually lands in 3-5 working days.
</example>
<example>
User: refund order 99
Assistant: [calls lookup_order(order_id="99")] -> not found
I can't find order 99. Could you check the number on your confirmation email?
</example>
"""
```

- **Two or three is enough.** Past that you pay tokens on every call for little gain.
- **Vary them on purpose.** If every example is a happy path, the model will make
  every case look like one. Include one where the right move is to refuse, ask, or
  report a failure.
- **Expect them to be copied too closely.** If both examples say "$42.10", you will
  start seeing $42.10 in real answers. Use visibly different values.
- **Wrap them in tags** (`<example>`) so the model can tell an example apart from the
  real conversation.
- **They take a place in the budget.** Give them a priority in the `PromptBuilder`,
  usually right after the rules.

### Prompts are code: version them

Your system prompt changes your agent's behaviour as much as a code change does, so
treat it like code:

- **Keep prompts in files under git**, not as strings scattered through the code.
  Diffs and blame then work on them.
- **Give each one an id and a version** (`support_agent@v14`) and **record that id on
  every trace** (Chapter 12). "Quality dropped on Tuesday" is only answerable if you
  know which prompt was live on Tuesday.
- **Never edit a prompt in production without running the evals** (Chapters 10–11).
  "Just a wording tweak" is how most silent regressions start.
- **Pin the model alongside the prompt.** A prompt tuned on one model is a different
  prompt on another one.

## 7. Common mistakes

1. **Forgetting the output reserve.** Truncated answers, mysteriously.
2. **Slicing the message list.** 400s that only appear in long sessions. See §4.
3. **Unbounded tool results.** One file read, one dead run.
4. **Truncating the tail of an error.** You keep the boilerplate and cut the cause.
5. **Compaction that loses "what we already tried".** The agent loops on dead ends.
6. **Summarising the recent turns too.** Now it has no idea what state it is in.
7. **Mid-conversation `system` messages.** Silently ignored, or a 400.
8. **Assuming a big window means no work needed.** Cost and attention both still bite.
9. **Measuring tokens with `len(text)` instead of `/4`.** Off by 4x, every time.
10. **Few-shot examples that are all happy paths.** The model never refuses or asks.
11. **Prompts edited in place with no version id.** Regressions you can't date.

## 8. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_budget.py` | `ContextBudget`, `PromptBuilder` |
| 2 | `exercise_2_pairs.py` | `message_pairs` — the atomic-unit grouping |
| 3 | `exercise_3_trim.py` | `trim_messages` — group-aware sliding window |
| 4 | `exercise_4_truncate.py` | `middle_out`, `truncate_tool_results` |
| 5 | `exercise_5_compact.py` | `render_transcript`, `compact` |
| 6 | `exercise_6_long_run.py` | **Integration:** an agent that survives a long session |

```bash
pytest chapters/ch04_context/tests -q
```

## 9. Check yourself

1. Four things share the context window. Name them.
2. Why must you reserve output tokens, and what goes wrong if you don't?
3. Which three messages form one atomic group, and what error do you get for splitting them?
4. Why cut the middle of a tool result rather than the end?
5. Why keep the FIRST turns as well as the last when using a sliding window?
6. Three things a good compaction prompt must preserve.
7. Why a `user` message for the summary rather than `system`?
8. What is "lost in the middle" and how does it change your prompt layout?
9. Your agent works fine at 20k tokens and gets noticeably dumber at 150k, with no
   errors. What's happening and what do you do?
10. What does "externalise" mean, and why is it better than compaction when available?
11. Why can two few-shot examples beat a page of rules? What is the risk of copying?
12. Why should every trace record the prompt version?

---

**Next:** Chapter 5 turns this into managed short-term memory — sessions that persist,
strategies that swap, and state that survives a restart.
