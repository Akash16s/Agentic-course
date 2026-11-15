"""Why naive slicing breaks a conversation. Free and offline.

    python chapters/ch04_context/examples/01_the_400_you_will_get.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.context import message_pairs, trim_messages

conversation = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "compare a.txt and b.txt"},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "read", "arguments": '{"p":"a.txt"}'}},
        {"id": "c2", "type": "function", "function": {"name": "read", "arguments": '{"p":"b.txt"}'}},
    ]},
    {"role": "tool", "tool_call_id": "c1", "name": "read", "content": "contents of a"},
    {"role": "tool", "tool_call_id": "c2", "name": "read", "content": "contents of b"},
    {"role": "assistant", "content": "a.txt is longer."},
    {"role": "user", "content": "by how much?"},
]


def show(label, messages):
    print(f"\n{label}")
    print("-" * 66)
    requested, answered = set(), set()
    for m in messages:
        for c in m.get("tool_calls") or []:
            requested.add(c["id"])
        if m["role"] == "tool":
            answered.add(m["tool_call_id"])
        marker = f"  tool_calls={[c['id'] for c in m['tool_calls']]}" if m.get("tool_calls") else ""
        marker += f"  answers={m['tool_call_id']}" if m["role"] == "tool" else ""
        print(f"  {m['role']:<10}{str(m.get('content'))[:28]:<30}{marker}")

    orphan_answers = answered - requested
    unanswered = requested - answered
    if orphan_answers:
        print(f"\n  BROKEN: tool results with no request: {sorted(orphan_answers)}")
        print("  -> 400: tool_call_id not found in preceding assistant message")
    elif unanswered:
        print(f"\n  BROKEN: requests with no results: {sorted(unanswered)}")
        print("  -> the model sees a question it asked and no answer")
    else:
        print("\n  VALID: every request has its result")


show("ORIGINAL", conversation)

print("\n" + "=" * 66)
print("THE NAIVE FIX: keep the last 4 messages")
print("=" * 66)
show("messages[-4:]", conversation[-4:])

print("\n" + "=" * 66)
print("THE CORRECT FIX: group first, then drop whole groups")
print("=" * 66)
print("\ngroups:")
for i, g in enumerate(message_pairs(conversation)):
    print(f"  {i}: {[m['role'] for m in g]}")
show("trim_messages(..., keep_last=2)", trim_messages(conversation, 30, keep_last=2))

print("""
The naive slice looks fine in a code review and works for every conversation you
test by hand, because short conversations never get trimmed. It breaks the first
time a real user has a long session.""")
