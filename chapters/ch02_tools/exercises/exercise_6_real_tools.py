"""EXERCISE 6 — A real agent with real tools (one manual turn of the loop).

No automated test. Run it, watch it work, then break it on purpose.

    python chapters/ch02_tools/exercises/exercise_6_real_tools.py

TASKS
  1. Write three tools with GOOD docstrings:
       calculate(expression: str) -> str
           Evaluate an arithmetic expression. Do NOT use eval() on raw input —
           that is a remote code execution hole and Chapter 14 will come back to it.
           Use `ast.literal_eval` for literals, or a small operator-whitelist walker
           over `ast.parse(expr, mode="eval")`. Reject anything else.
       read_file(path: str) -> str
           Read a UTF-8 text file. Return an error string for missing files,
           and TRUNCATE long files (say 4000 chars) — an unbounded tool result
           can blow your whole context window in one call.
       list_files(directory: str = ".") -> list[str]
           List a directory.
  2. Register them, send a question, and print:
       - the raw tool_calls the model produced
       - the tool messages you send back
       - the final answer
  3. Then EXPERIMENT (this is the actual exercise):
       a. Ask "what is 847 * 291?" — does it use the tool or do mental arithmetic?
          Try a small model and a strong one. The difference is instructive.
       b. Delete the `Args:` block from `calculate`'s docstring. Does argument
          quality drop?
       c. Rename `calculate` to `c` and empty its description. Watch it get ignored.
       d. Ask something needing two tools at once ("compare the sizes of a.txt and
          b.txt") — do you get parallel tool_calls?
       e. Ask for a tool that does not exist. Read what your registry returns and
          check the model recovers.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.llm import LLMClient

# TODO: import your Tool/ToolRegistry work from this chapter's exercises,
#       or agentlib.tools if you want the reference versions.


def main() -> None:
    client = LLMClient()
    # TODO 1: define the three tools
    # TODO 2: registry = ToolRegistry([...])
    # TODO 3: messages = [{"role": "user", "content": "what is 847 * 291?"}]
    # TODO 4: response = client.chat(messages, tools=registry.specs())
    # TODO 5: if response.wants_tools: parse, execute, append, call again
    # TODO 6: print the final text
    raise NotImplementedError


if __name__ == "__main__":
    main()
