"""See what @tool actually produces. No API key needed, no cost.

    python chapters/ch02_tools/examples/01_schema_generation.py
"""

import json
import sys
from pathlib import Path
from typing import Literal, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.tools import ToolRegistry, tool


@tool
def search_documents(
    query: str,
    limit: int = 10,
    scope: Literal["all", "policies", "projects"] = "all",
    after: Optional[str] = None,
) -> list[str]:
    """Search the internal knowledge base for documents matching a query.

    Use this when the user asks about company policy, past projects or internal
    docs. Do NOT use it for general knowledge questions — answer those directly.

    Args:
        query: Natural-language search query. Keywords work better than sentences.
        limit: Maximum number of documents to return. Keep it under 20.
        scope: Which part of the knowledge base to search.
        after: Only return documents modified after this date, as YYYY-MM-DD.
    """
    return []


@tool
def s(q: str, n: int = 10) -> list[str]:
    return []


print("=" * 72)
print("A GOOD TOOL — this is what the model sees")
print("=" * 72)
print(json.dumps(search_documents.spec(), indent=2))

print("\n" + "=" * 72)
print("THE SAME FUNCTION, BADLY WRITTEN")
print("=" * 72)
print(json.dumps(s.spec(), indent=2))

print("\n" + "-" * 72)
print("Identical to Python. Worlds apart to a model:")
print("  * no description  -> it cannot tell WHEN to use the tool")
print("  * no param docs   -> it guesses at formats and units")
print("  * no enum         -> `scope` would be a free-text field it can invent values for")
print("  * `s`, `q`, `n`   -> names carry meaning; these carry none")

registry = ToolRegistry([search_documents])
overhead = len(json.dumps(registry.specs())) // 4
print(f"\nSchema cost: ~{overhead} tokens, resent on EVERY request in the conversation.")
print("Twenty tools like this is ~3,000 tokens of permanent overhead per call.")
