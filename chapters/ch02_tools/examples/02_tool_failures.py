"""The three ways a tool call fails — and why all three come back as data.

    python chapters/ch02_tools/examples/02_tool_failures.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.tools import ToolRegistry, tool


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b.

    Args:
        a: Numerator.
        b: Denominator.
    """
    return a / b


registry = ToolRegistry([divide])

cases = [
    ("happy path",              "divide",   {"a": 10, "b": 2}),
    ("hallucinated tool name",  "multiply", {"a": 10, "b": 2}),
    ("malformed JSON",          "divide",   '{"a": 10, "b":'),
    ("JSON that is not an object", "divide", "[10, 2]"),
    ("wrong parameter names",   "divide",   {"x": 10, "y": 2}),
    ("missing a required arg",  "divide",   {"a": 10}),
    ("the tool itself raises",  "divide",   {"a": 10, "b": 0}),
]

print(f"{'case':<30} {'err':<5} result")
print("-" * 92)
for label, name, args in cases:
    result = registry.execute(name, args)
    print(f"{label:<30} {str(result.is_error):<5} {result.content[:52]}")

print("-" * 92)
print("\nNot one of those raised. Every single one is a string the model can read,")
print("understand and act on:")
print("  'unknown tool'      -> it picks a real one from the list you gave it")
print("  'not valid JSON'    -> it re-emits the arguments")
print("  'invalid arguments' -> it fixes the field names")
print("  'ZeroDivisionError' -> it stops dividing by zero")
print("\nAn agent that recovers from its own mistakes is the whole point.")
print("An agent that crashes on the first typo is a script with extra steps.")
