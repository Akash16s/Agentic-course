"""A real tool call against the real API. Needs your key.

    python chapters/ch02_tools/examples/03_real_tool_call.py
"""

import json
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.conversation import Conversation
from agentlib.llm import LLMClient
from agentlib.tools import ToolRegistry, execute_tool_calls, parse_tool_calls, tool

CALLS_MADE: list[str] = []


@tool
def get_weather(city: str, unit: Literal["c", "f"] = "c") -> dict:
    """Look up the current weather for a city.

    Args:
        city: City name, e.g. "Delhi".
        unit: Temperature unit, celsius or fahrenheit.
    """
    CALLS_MADE.append(f"get_weather({city!r}, {unit!r})")
    fake = {"Delhi": 34, "Mumbai": 29, "London": 12}
    temp = fake.get(city, 20)
    if unit == "f":
        temp = round(temp * 9 / 5 + 32)
    return {"city": city, "temperature": temp, "unit": unit, "conditions": "clear"}


client = LLMClient()
registry = ToolRegistry([get_weather])
conv = Conversation("You are a concise weather assistant.")
conv.add_user("Is it warmer in Delhi or Mumbai right now? Answer in one sentence.")

for turn in range(1, 6):
    response = client.chat(conv.messages, tools=registry.specs(), max_tokens=500)
    conv.add_response(response)

    print(f"\n--- turn {turn} " + "-" * 56)
    print(f"finish_reason : {response.finish_reason}")
    print(f"content       : {response.text!r}")
    print(f"tool_calls    : {len(response.tool_calls)}")
    for call in response.tool_calls:
        print(f"   -> {call['function']['name']}({call['function']['arguments']})")

    if not response.wants_tools:
        print(f"\nFINAL: {response.text}")
        break

    results = execute_tool_calls(registry, parse_tool_calls(response))
    for message in results:
        print(f"   <- {message['content'][:80]}")
    conv.extend(results)

print("\n" + "=" * 70)
print("tools actually executed:", CALLS_MADE or "none")
print("\nNotice: on the tool turn, `content` was None or empty — the model said")
print("nothing at all. Calling .strip() on it is a production crash waiting to happen.")
print("\nIf you got both cities in ONE turn, that was parallel tool calling.")
