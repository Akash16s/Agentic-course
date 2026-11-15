"""The agent loop written out longhand, with a fake model. Free, offline, instant.

Read this next to agentlib/agent.py. This is the same thing with the safety rails
removed so you can see the shape.

    python chapters/ch03_react_loop/examples/01_loop_by_hand.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.conversation import Conversation
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, execute_tool_calls, parse_tool_calls, tool


@tool
def get_population(city: str) -> int:
    """Population of a city."""
    return {"Delhi": 32_900_000, "Mumbai": 21_300_000}.get(city, 0)


registry = ToolRegistry([get_population])

client = FakeLLMClient([
    tool_response(tool_call("get_population", {"city": "Delhi"}, call_id="c1")),
    tool_response(tool_call("get_population", {"city": "Mumbai"}, call_id="c2")),
    "Delhi is larger, with about 32.9 million people to Mumbai's 21.3 million.",
])

conversation = Conversation("You are a concise assistant.")
conversation.add_user("Which is bigger, Delhi or Mumbai?")

MAX_STEPS = 10

for step in range(MAX_STEPS):                    # <- a bounded for, never `while True`
    print(f"\n{'=' * 66}\nSTEP {step}")

    response = client.chat(conversation.messages, tools=registry.specs())
    conversation.add_response(response)          # <- BEFORE the tool results

    calls = parse_tool_calls(response)
    print(f"  text       : {response.text!r}")
    print(f"  tool_calls : {[c.name for c in calls]}")

    if not calls:
        print(f"\n{'=' * 66}\nDONE after {step + 1} steps: {response.text}")
        break

    results = execute_tool_calls(registry, calls)
    for message in results:
        print(f"  <- {message['name']}: {message['content']}")
    conversation.extend(results)
else:
    print(f"\nSTOPPED at max_steps={MAX_STEPS} without an answer")

print(f"\nfinal message list ({len(conversation.messages)} messages):")
for message in conversation.messages:
    preview = str(message.get("content"))[:48]
    extra = " +tool_calls" if message.get("tool_calls") else ""
    print(f"  {message['role']:<10} {preview}{extra}")
