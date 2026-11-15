"""Proof that the model has no memory, and that YOU are the memory.

Run this. It is the single most important 30 seconds of the chapter.

    python chapters/ch01_agent_loop/examples/03_stateless_proof.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.llm import LLMClient

client = LLMClient()

# ---------------------------------------------------------------- experiment 1
print("=" * 70)
print("1. TWO SEPARATE CALLS  (no history passed)")
print("=" * 70)

client.chat([{"role": "user", "content": "My name is Akash. Remember it."}], max_tokens=50)
r = client.chat([{"role": "user", "content": "What is my name?"}], max_tokens=50)
print("Q: What is my name?")
print("A:", r.text)
print("\n-> It has no idea. The first call left no trace anywhere.\n")

# ---------------------------------------------------------------- experiment 2
print("=" * 70)
print("2. ONE CALL WITH THE HISTORY RESENT")
print("=" * 70)

history = [
    {"role": "user", "content": "My name is Akash. Remember it."},
    {"role": "assistant", "content": "Got it, Akash."},
    {"role": "user", "content": "What is my name?"},
]
r = client.chat(history, max_tokens=50)
print("Q: What is my name?  (with 3 messages of history)")
print("A:", r.text)
print(f"\n-> It 'remembers'. Note prompt_tokens went up: {r.usage.prompt_tokens}")
print("   The memory is in YOUR list, not in the model.\n")

# ---------------------------------------------------------------- experiment 3
print("=" * 70)
print("3. FABRICATING THE PAST")
print("=" * 70)
print("The model cannot tell the difference between a reply it actually produced")
print("and one you typed into the history yourself. Watch:\n")

fake_history = [
    {"role": "user", "content": "What is the secret code?"},
    {"role": "assistant", "content": "The secret code is BANANA-42."},  # never happened
    {"role": "user", "content": "Repeat the secret code."},
]
r = client.chat(fake_history, max_tokens=50)
print("A:", r.text)
print("\n-> This is a superpower (few-shot prompting, steering, recovery) AND a")
print("   security hole (Chapter 14). Anyone who can write into the message list")
print("   can put words in the model's mouth.")
