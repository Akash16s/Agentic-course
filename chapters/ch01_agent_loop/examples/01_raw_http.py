"""An LLM call with NO SDK. This is the whole of it.

Read this file before anything else in the chapter. Once you have seen that a model call
is one HTTP POST with a JSON body, no framework can ever mystify you again.

    python chapters/ch01_agent_loop/examples/01_raw_http.py
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("AGENT_MODEL", "anthropic/claude-haiku-4.5")

if not API_KEY:
    sys.exit("Set OPENROUTER_API_KEY in .env first (see SETUP.md).")

# ---------------------------------------------------------------- the request
request_body = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "You answer in exactly one short sentence."},
        {"role": "user", "content": "Why is the sky blue?"},
    ],
    "temperature": 0.0,
    "max_tokens": 100,
}

print("=" * 70)
print("REQUEST  POST https://openrouter.ai/api/v1/chat/completions")
print("=" * 70)
print(json.dumps(request_body, indent=2))

response = httpx.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json=request_body,
    timeout=60,
)

print("\n" + "=" * 70)
print(f"RESPONSE  HTTP {response.status_code}")
print("=" * 70)
payload = response.json()
print(json.dumps(payload, indent=2)[:2000])

# ------------------------------------------------------------ the useful bits
if response.status_code == 200:
    choice = payload["choices"][0]
    usage = payload.get("usage", {})
    print("\n" + "-" * 70)
    print("text          :", choice["message"]["content"])
    print("finish_reason :", choice["finish_reason"])
    print("tokens        : in=%s out=%s" % (
        usage.get("prompt_tokens"), usage.get("completion_tokens")))
    print("-" * 70)
    print("\nThings to try:")
    print("  * set max_tokens to 5   -> finish_reason becomes 'length'")
    print("  * set temperature to 2  -> watch it lose its mind")
    print("  * misspell the model id -> see the 400 (and note: retrying won't help)")
