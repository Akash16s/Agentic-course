"""The same call through `agentlib.llm.LLMClient`.

Compare with 01_raw_http.py. The wrapper adds: a normalised response object, our own
error types, and a single place to change the model. That is all. Thin is the point.

    python chapters/ch01_agent_loop/examples/02_with_client.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib import errors
from agentlib.llm import LLMClient
from agentlib.pricing import cost_usd

client = LLMClient()
print(f"model: {client.model}\n")

try:
    response = client.chat(
        [
            {"role": "system", "content": "You answer in exactly one short sentence."},
            {"role": "user", "content": "Why is the sky blue?"},
        ],
        max_tokens=100,
    )
except errors.LLMError as exc:
    sys.exit(f"call failed: {type(exc).__name__}: {exc}  (retryable={exc.retryable})")

print("text      :", response.text)
print("finish    :", response.finish_reason, "(truncated)" if response.truncated else "")
print("usage     :", response.usage)
print("cost      : $%.6f" % cost_usd(response.model, *response.usage.__dict__.values()))

print("\n--- the raw payload is always there when you need it ---")
print(str(response.raw)[:300], "...")
