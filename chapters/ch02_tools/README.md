# Chapter 2 — Tools & Function Calling

**Time: ~6 hours** (50 min reading · 40 min examples · 3.5 hrs exercises · 1 hr review)
**Prerequisite:** Chapter 1 green.

---

## After this chapter you can

- Explain exactly what "function calling" is, and why the model never runs anything
- Turn any Python function into a tool the model can request, automatically
- Generate JSON Schema from type hints and docstrings
- Build a tool registry that dispatches safely and never crashes your agent
- Handle the three ways a tool call goes wrong, all as data the model can recover from
- Write tool descriptions that a model actually uses correctly

---

## 1. The one idea

**A tool is a JSON Schema description of a function, plus the function.**

You send the *schema*. The model sends back a *request*. You run the *function*.

```
     YOU                          MODEL                       YOU
      │                             │                          │
      │ here are 3 tools            │                          │
      │ (name, description, schema) │                          │
      ├────────────────────────────►│                          │
      │                             │ "I'd like get_weather    │
      │                             │  with {"city":"Delhi"}"  │
      │◄────────────────────────────┤                          │
      │                                                        │
      │  ── you parse it, you validate it, YOU run it ─────────►│
      │                                                        │
      │◄───────────────────────────────────────────────────────┤
      │  result: "32C, clear"                                  │
      │                             │                          │
      │ role:tool -> "32C, clear"   │                          │
      ├────────────────────────────►│                          │
      │                             │ "It's 32C and clear      │
      │◄────────────────────────────┤  in Delhi today."        │
```

The model is doing one thing only: producing text that happens to be shaped like a
function call, because it was fine-tuned on millions of examples of exactly that shape.
There is no sandbox, no execution, no capability. **Every single thing your agent can do
to the world, you gave it.** That is worth remembering in Chapter 14.

## 2. What goes on the wire

### The request — you add a `tools` array

```json
{
  "model": "anthropic/claude-haiku-4.5",
  "messages": [{"role": "user", "content": "weather in Delhi?"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Look up the current weather for a city.",
      "parameters": {
        "type": "object",
        "properties": {
          "city": {"type": "string", "description": "City name, e.g. \"Delhi\""},
          "unit": {"type": "string", "enum": ["c", "f"], "description": "Temperature unit"}
        },
        "required": ["city"]
      }
    }
  }]
}
```

That `parameters` object is **JSON Schema**. It is the only thing standing between you and
the model sending `{"town": "Delhi"}` or `{"city": ["Delhi"]}`.

### The response — `finish_reason: "tool_calls"`

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {"name": "get_weather", "arguments": "{\"city\": \"Delhi\"}"}
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

Three things to notice, all of which bite people:

1. **`content` is `null`.** The model said nothing. If your code does
   `response.text.strip()` here, you get an AttributeError in production at 2am.
2. **`arguments` is a STRING**, not an object. It's JSON *inside* JSON. You must
   `json.loads` it, and it can be malformed — smaller models produce broken JSON
   regularly.
3. **`id` matters.** When the model asks for three tools at once, the `tool_call_id` on
   each result is the only thing pairing answers to questions.

### Sending the result back

```json
{"role": "tool", "tool_call_id": "call_abc123", "name": "get_weather", "content": "32C, clear"}
```

**The assistant message with the `tool_calls` must be in the history too**, before the
tool messages. The sequence is always:

```
user → assistant(tool_calls) → tool(result) → assistant(text)
                ▲                    ▲
                └── both of these ───┘  must be in your message list
```

Drop the assistant message and you are sending the model an answer to a question it can
see no record of asking. Every provider rejects that with a 400.

## 3. Schema generation: why we automate it

You *could* hand-write those schema dicts. Nobody does, twice. They drift from the
function the moment someone adds a parameter, and a drifted schema is a silent bug: the
model dutifully sends the old field name and your function raises TypeError.

So we derive the schema from the function itself — its signature, type hints and
docstring are already the specification:

```python
@tool
def get_weather(city: str, unit: Literal["c", "f"] = "c") -> str:
    """Look up the current weather for a city.

    Args:
        city: City name, e.g. "Delhi".
        unit: Temperature unit.
    """
```

That decorator produces the whole JSON blob above. Rename the parameter and the schema
follows. This is what `@tool` in every framework does, and it is about 80 lines.

### The type mapping

| Python | JSON Schema | Note |
|---|---|---|
| `str` | `{"type": "string"}` | |
| `int` | `{"type": "integer"}` | |
| `float` | `{"type": "number"}` | JSON has no int/float split, hence two names |
| `bool` | `{"type": "boolean"}` | |
| `list[int]` | `{"type": "array", "items": {"type": "integer"}}` | |
| `dict` | `{"type": "object"}` | |
| `Literal["a","b"]` | `{"type": "string", "enum": ["a","b"]}` | **the most valuable one** |
| `int \| None` | `{"type": "integer"}`, not required | Optional means "may be omitted" |

**Use `Literal` everywhere you can.** An enum is a hard constraint the model can see. A
description saying "must be one of c or f" is a suggestion it will sometimes ignore.

### What "required" really means

A parameter is required when it has **no default AND is not Optional**. Get this wrong in
the strict direction and the model refuses to call your tool without a field it has no
way to know. Get it wrong in the loose direction and your function raises TypeError.

## 4. Descriptions are prompt engineering

The schema is the only documentation the model gets. These two tools are identical to
Python and worlds apart to a model:

```python
def s(q: str, n: int = 10): ...            # description: "s"

def search_documents(query: str, limit: int = 10):
    """Search the internal knowledge base for documents matching a query.

    Use this when the user asks about company policy, past projects or internal
    docs. Do NOT use it for general knowledge questions — answer those directly.

    Args:
        query: Natural-language search query. Keywords work better than sentences.
        limit: Maximum number of documents to return. Keep it under 20.
    """
```

Rules that actually move the needle:

- **Say when NOT to use it.** Over-calling is more common than under-calling. A model
  handed a search tool will search for "what is 2+2".
- **Name things the way the model thinks.** `get_user_by_email` beats `fetch_usr`.
- **Put units, formats and examples in the parameter description.** "date in YYYY-MM-DD"
  saves you a validation round trip every time.
- **Keep the tool count low.** Quality drops noticeably past ~15-20 tools. If you need
  more, group them or route (Chapter 8).
- **Every tool costs input tokens on every single call**, forever, because the schemas
  are resent every turn. Twenty verbose tools can be 3,000 tokens of overhead per request.

## 5. Failure is data, not an exception

Three distinct things go wrong, and all three must come back as **a tool result the model
can read**, never as a Python exception that kills the loop:

| Failure | Why it happens | What you return |
|---|---|---|
| **Unknown tool name** | Model hallucinated a tool, or you removed one mid-conversation | `"unknown tool 'x'. Available: a, b, c"` |
| **Malformed JSON arguments** | Small models truncate or mangle JSON, especially with `max_tokens` too low | `"arguments were not valid JSON: <parser error>"` |
| **The tool itself raised** | File missing, API down, bad input | `"FileNotFoundError: no such file 'x'"` |

Why return them instead of raising? **Because the model can fix all three.** Tell it the
tool doesn't exist and it picks a real one. Tell it the JSON was broken and it re-emits it.
Tell it the file is missing and it lists the directory first. An agent that recovers from
its own mistakes is the entire point; an agent that crashes on the first typo is a script.

The one thing you should NOT swallow: errors in *your own* orchestration code. A bug in
your registry is not something the model can fix, and hiding it behind a polite tool
message will cost you a day of debugging.

## 6. Parallel tool calls

Modern models often request several tools in one turn:

```json
"tool_calls": [
  {"id": "c1", "function": {"name": "get_weather", "arguments": "{\"city\":\"Delhi\"}"}},
  {"id": "c2", "function": {"name": "get_weather", "arguments": "{\"city\":\"Mumbai\"}"}}
]
```

Rules:
- **One `role: tool` message per call.** Always. Even for the ones that failed.
- **Order matters less than completeness**, but keep request order anyway; it's free.
- They are independent, so you can run them concurrently — we do that in Chapter 3, once
  the loop exists to hang it on.

## 7. Common mistakes

1. **`response.text.strip()` when `content` is `null`.** Check `wants_tools` first.
2. **Forgetting to append the assistant message that contains the tool_calls.** Instant 400.
3. **Forgetting `tool_call_id`.** Works by luck with one tool, breaks with two.
4. **`json.loads` without a try/except.** Malformed arguments are routine, not exotic.
5. **Letting a tool exception escape.** One bad file path kills a 40-step run.
6. **Hand-written schemas that drift from the function.** Derive them.
7. **`required` containing every parameter** because you didn't check for defaults.
8. **Returning a Python object from a tool.** It has to become a string; decide *how* it
   becomes a string, or `str(dict)` will send the model single-quoted pseudo-JSON.
9. **Thirty tools "just in case".** Accuracy falls off a cliff and every call pays for it.

## 8. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_schema.py` | `python_type_to_json_schema`, `is_optional` |
| 2 | `exercise_2_docstring.py` | `parse_docstring` — Google-style summary + params |
| 3 | `exercise_3_build_tool.py` | `build_tool` — signature + hints + docs → a `Tool` |
| 4 | `exercise_4_registry.py` | `ToolRegistry` — register, specs, safe dispatch |
| 5 | `exercise_5_execute.py` | `parse_tool_calls`, `tool_result_message`, `execute_tool_calls` |
| 6 | `exercise_6_real_tools.py` | **Integration:** a calculator + file-reader agent (needs your key) |

```bash
pytest chapters/ch02_tools/tests -q
```

## 9. Check yourself

1. Who executes a tool? What does the model actually produce?
2. `arguments` arrives as what Python type? What must you do to it, and what can go wrong?
3. What three messages must be in the history after one successful tool call, in order?
4. What does `tool_call_id` pair up, and when does omitting it start to hurt?
5. When is a parameter `required`?
6. Why is `Literal["a","b"]` better than a description saying "use a or b"?
7. Name the three tool failures and say why each is returned rather than raised.
8. Your agent has 30 tools and picks the wrong one constantly. Two things to try?
9. Why does adding a tool make *every* request in the conversation more expensive?
10. What should a tool description say besides what the tool does?

## 10. Going deeper

- OpenAI docs → Function calling; Anthropic docs → Tool use. Read both; the differences
  are where OpenRouter's abstraction leaks.
- json-schema.org → the spec for `parameters`. You only ever need `type`, `properties`,
  `required`, `enum`, `items`, `description`.

---

**Next:** Chapter 3 turns this into an actual loop — the model calls a tool, sees the
result, calls another, and keeps going until it's done.
