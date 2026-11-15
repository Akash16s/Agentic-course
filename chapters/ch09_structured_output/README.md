# Chapter 9 — Structured Output & Reliability

**Time: ~4 hours** (35 min reading · 25 min examples · 2.5 hrs exercises · 30 min review)
**Prerequisite:** Chapters 1–8 green.

---

## After this chapter you can

- Get JSON out of a text generator reliably, including from models that wrap it in prose
- Write a JSON Schema validator and know exactly what a schema does and doesn't constrain
- Build a repair loop that fixes bad output in one round trip instead of three
- Layer guardrails in an order that doesn't defeat itself
- Say which of the four techniques to reach for, and when

---

## 1. The one idea

**An LLM produces text. Your program needs data. Everything here is about that gap.**

You already closed it once: tool calling (Chapter 2) is schema-constrained output for
*actions*. This chapter is the other half — when the model's **answer** is data, not
prose:

```python
{"sentiment": "negative", "urgency": 4, "topics": ["billing", "refund"]}
```

Four techniques, in the order you should try them:

| Technique | Reliability | Cost | Use when |
|---|---|---|---|
| **1. Native structured output** | ~100% | free | your provider supports it |
| **2. Tool calling as a schema** | very high | free | you have tools anyway |
| **3. Prompt + parse + validate** | 85–98% | free | the universal fallback |
| **4. Repair loop** | ~99.9% | 1 extra call when it fires | on top of 3 |

Most people jump to 3 and stop. The order matters.

### 1. Native structured output

OpenAI's `response_format: {"type": "json_schema", ...}` and equivalents constrain
generation itself — the sampler is only allowed to emit tokens that keep the output
valid. It **cannot** produce invalid JSON. (How that works is in Track C.)

Availability is the catch. **Through OpenRouter, support varies by underlying model**,
and a request that works against one model 404s or silently ignores the parameter
against another. Always keep a fallback; never assume the constraint applied.

### 2. Tool calling as a schema

A trick worth knowing: define a tool whose only job is to receive your answer.

```python
@tool
def submit_analysis(sentiment: Literal["positive","negative","neutral"],
                    urgency: int, topics: list[str]) -> str:
    """Submit your analysis of the message."""
```

Force it with `tool_choice`, and the model's arguments *are* your structured output.
Tool-calling paths are heavily trained and well constrained, so this is usually more
reliable than asking for JSON in prose — and you already built all of it in Chapter 2.

### 3 & 4. Prompt, parse, validate, repair

The universal fallback, and the rest of this chapter.

## 2. Extraction: what models actually send you

Ask for JSON, get any of these:

```
{"a": 1}                              clean
```json\n{"a": 1}\n```                  fenced
Sure! Here's the JSON: {"a": 1}        prose before
{"a": 1, "b": [1, 2,],}                trailing commas
json {"a": 1}                          a stray label
```

A robust extractor tries several candidate substrings in order: the whole string, any
fenced block, the widest `{...}` or `[...]` span. Then strips trailing commas and
tries again.

**Where to stop.** Do not fix single quotes or unquoted keys. Past a point you are
writing a JavaScript parser, and the correct move is to send the error back to the
model — it fixes its own output more accurately than your regex guesses at what it
meant.

## 3. Validation

Parsing gives you *a* dict. Validation tells you it's *the* dict.

The subset of JSON Schema worth implementing: `type`, `properties`, `required`,
`enum`, `items`, `additionalProperties`, `minimum`/`maximum`,
`minLength`/`maxLength`, `minItems`/`maxItems`. That covers essentially every schema
you will hand a model.

Two design decisions that matter more than the code:

**Return a list of errors, don't raise.** The list goes straight back to the model as
repair instructions.

**Collect ALL errors, don't stop at the first.** One round trip fixing four problems
beats four round trips fixing one each. This is the difference between a repair loop
that costs one extra call and one that costs four.

### The Python gotcha in the type table

```python
isinstance(True, int)   # True  — bool subclasses int in Python
```

JSON says boolean and integer are different types. So:

```python
"integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
```

Without that `and not`, `{"age": true}` validates against `{"type": "integer"}`. It's
the kind of bug that sits in a validator for a year.

## 4. The repair loop

```python
value = extract_json(raw)
errors = validate(value, schema)
if errors:
    raw = call_model(repair_prompt(errors, schema, raw))   # try again
```

**Be specific.** This is the whole difference between a repair loop that works and one
that doesn't:

```
BAD   "That was invalid. Try again."
GOOD  "Validation errors:
       - $.items[2].price: expected number, got str
       - $: missing required field 'currency'"
```

Told the second, a model fixes it on the next attempt essentially always. Told the
first, it re-emits something similar and you burn another call.

**Cap at 2–3 attempts.** Two fixes the overwhelming majority. If it fails three times,
**the schema is the problem, not the model** — and the fix is usually to flatten it.
Models are markedly worse at deeply nested objects than at flat ones. Two levels is
comfortable; five is asking for trouble.

## 5. Schema design for models

The schema is a prompt. Write it like one.

- **Descriptions on every field.** `{"type": "string", "description": "ISO 8601 date,
  e.g. 2026-09-20"}` prevents an entire class of retry.
- **`enum` over free text**, always, where the value set is known.
- **Flat over nested.** Two levels max if you can manage it.
- **Short field names** — they cost output tokens on every single response.
- **`additionalProperties: false`** when you want to catch the model inventing fields.
  Leave it off when you'd rather tolerate extras than fail.
- **Don't demand a field the model cannot know.** If `confidence` isn't derivable from
  what you gave it, you have asked it to make a number up, and it will.

## 6. Guardrails

Checks on the way out. Each guard can **reject** or **rewrite**:

```python
run_guardrails(answer, [
    RedactPII(),                      # rewrites
    Blocklist(["internal-only"]),     # rejects
    MaxLength(2000, truncate=True),   # rewrites
])
```

**Order is a design decision, not an implementation detail.** Rewriting guards go
before rejecting guards — otherwise you reject text that redaction would have made
acceptable, and the user gets an error where they should have got an answer.

**Run every guard even after one fails.** The report should list all the problems, for
the same reason validation collects all errors.

Guardrails are output-side only. Input-side defence — prompt injection, tool
permissions, sandboxing — is Chapter 14, and it is a different problem.

## 7. Common mistakes

1. **Assuming native structured output is available.** Through a proxy it varies by
   model. Always keep the fallback.
2. **`json.loads(response.text)` with no try/except.** It works until it doesn't.
3. **Fixing single quotes with regex.** You are writing a parser. Ask the model.
4. **Validation that raises on the first error.** Turns one repair call into four.
5. **`isinstance(v, int)` for integers.** `True` passes.
6. **A vague repair message.** "Invalid, try again" gets you invalid again.
7. **Unlimited repair attempts.** After three, fix the schema.
8. **Deeply nested schemas.** Flatten before you retry.
9. **Fields with no description.** Every ambiguity becomes a retry.
10. **Rejecting guards before redacting guards.** Errors where answers were possible.
11. **Requiring a field the model cannot know.** You asked it to invent; it obliged.

## 8. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_extract.py` | `extract_json` — fences, prose, trailing commas |
| 2 | `exercise_2_validate.py` | `validate` — the JSON Schema subset |
| 3 | `exercise_3_repair.py` | `repair_prompt`, `extract_validated` |
| 4 | `exercise_4_guardrails.py` | `Guardrail`, `MaxLength`, `Blocklist`, `RedactPII`, `run_guardrails` |
| 5 | `exercise_5_extractor.py` | **Integration:** a real structured extractor, four ways |

```bash
pytest chapters/ch09_structured_output/tests -q
```

## 9. Check yourself

1. Four techniques, in order of preference. Why is that the order?
2. Why is tool calling often more reliable than asking for JSON in prose?
3. Name four things a model puts around JSON that break `json.loads`.
4. Where should an extractor stop trying to repair text itself, and why?
5. Why does `validate` return a list rather than raising?
6. Why collect all errors instead of stopping at the first? Quantify it.
7. What's wrong with `isinstance(v, int)` as an integer check?
8. Give a bad repair message and a good one.
9. Your repair loop fails three times running. What's the most likely cause?
10. Why must redacting guards run before rejecting guards?
11. You need a `confidence` field. What has to be true for that to be a fair ask?

---

**Next:** Chapter 10 — you have built a lot. Time to find out whether any of it works.
