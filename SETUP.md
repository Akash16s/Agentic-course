# Setup — do this once (20 minutes)

## 1. Virtual environment

```bash
cd Agentic-course    # wherever you cloned it
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11+ is assumed. (If you already have a working `.venv/`, just activate it.)

Worth installing `uv` at some point (`brew install uv`) since CS336 next door uses it,
but nothing here requires it.

Every time you open a new terminal for this course:
```bash
cd Agentic-course && source .venv/bin/activate
```

## 2. Your OpenRouter key

```bash
cp .env.example .env
```

Open `.env` and paste your key after `OPENROUTER_API_KEY=`.

**Why OpenRouter is a good choice for this course:** it speaks the OpenAI API format but
routes to ~every model — Anthropic, OpenAI, Google, Meta, Qwen, DeepSeek. One key, one bill,
and you can swap `anthropic/claude-haiku-4.5` for `openai/gpt-4o-mini` by changing one string.
That is *exactly* the abstraction we want while learning, because it forces us to write code
that is not glued to one vendor.

**The catch, and remember it:** OpenRouter is a proxy. A few provider-specific features
(Anthropic's prompt caching controls, some structured-output modes) behave differently or are
unavailable through it. We will call that out when it matters, in Chapter 13.

## 3. Check your credit and pick a model

```bash
python chapters/ch01_agent_loop/examples/00_check_setup.py
```

That script verifies your key, prints your credit balance, and lists some cheap
tool-calling-capable models with their prices. **Model IDs change.** If the default in `.env`
404s, run that script and pick a live one.

## 4. Budget

The whole of Track A costs roughly **$3–15** in API spend if you use a cheap model for
development. Habits that keep it near the bottom of that range:

- Develop against a small model (`claude-haiku-4.5`, `gpt-4o-mini`, `gemini-2.0-flash`).
  Only run the big model when you are specifically comparing quality.
- Keep `max_tokens` low while iterating. A runaway agent loop is how people burn $40 by
  accident — which is exactly why Chapter 1 makes you build a cost tracker before anything else.
- The tests in every chapter run **offline** against fake clients. You will not spend a cent
  running `pytest`.

## 5. Sanity check

```bash
pytest chapters/ch01_agent_loop/tests -q
```

You should see failures — those are your exercises, not a broken setup. If you see *import*
errors instead, the environment is wrong; fix that first.
