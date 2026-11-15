"""EXERCISE 4 — The filesystem as memory.

WHY: The context window is small, expensive and forgets everything when the run
ends. The disk is huge, free and permanent. Long-running agents use files the way
you use a notebook: write down findings and plans, read back only what the current
step needs, and park huge tool outputs on disk with a pointer instead of pasting
them into the conversation.

    pytest chapters/ch08b_harness/tests -q -k workspace
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agentlib.security import sandbox_path
from agentlib.tools import Tool, build_tool

#: Allowed characters for an offload file prefix (tool names fit this).
PREFIX = re.compile(r"^[A-Za-z0-9_-]+$")


class Workspace:
    """A sandboxed folder of notes. Every path goes through `self.path()`.

    The constructor is given — the work is in the methods.
    """

    def __init__(self, root: str | Path, *, max_read_chars: int = 4000,
                 max_note_chars: int = 100_000) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_read_chars = max_read_chars
        self.max_note_chars = max_note_chars

    def path(self, name: str) -> Path:
        """Resolve `name` inside the workspace.

        Spec:
          * use `sandbox_path(self.root, name)` from agentlib.security (Chapter 14);
            let its PathEscape propagate for "../x", "/etc/passwd" and friends
          * if the result IS the root itself (name "." or "") -> ValueError
        """
        # TODO: implement
        raise NotImplementedError

    def write_note(self, name: str, content: str, append: bool = False) -> str:
        """Write (or append) text. Returns f"wrote {n} chars to {name}" or
        f"appended {n} chars to {name}" where n = len(content).

        Spec:
          * len(content) > max_note_chars -> ValueError mentioning the 'limit'
          * create parent folders as needed ("notes/day1/log.md" just works)
          * utf-8
        """
        # TODO: implement
        raise NotImplementedError

    def read_note(self, name: str, offset: int = 0, limit: int | None = None) -> str:
        """Read a chunk of a note.

        Spec:
          * not an existing file -> FileNotFoundError(f"no note named {name!r}")
          * limit = max_read_chars if None, else min(limit, max_read_chars)
          * offset = max(0, offset); chunk = text[offset : offset + limit]
          * if the chunk stops before the end of the file, append
              f"\\n...[showing chars {offset}-{end} of {len(text)}; "
              f"call read_note with offset={end} to continue]"
            where end = offset + len(chunk)

        The hint tells the model exactly how to get the next piece. Without it, a
        model that receives the first 4,000 chars of a file will usually assume
        that is the whole file.
        """
        # TODO: implement
        raise NotImplementedError

    def list_notes(self) -> list[str]:
        """Every file under the root, recursively, as sorted POSIX paths relative to
        the root ("a.md", "a/z.md", "b.md")."""
        # TODO: implement
        raise NotImplementedError

    def grep_notes(self, pattern: str, *, ignore_case: bool = True,
                   max_matches: int = 50) -> list[str]:
        """Regex search over every note, in list_notes() order.

        Spec:
          * bad regex -> ValueError mentioning the 'pattern'
          * each hit: f"{name}:{lineno}: {line.strip()[:200]}"  (lineno from 1)
          * stop as soon as you have max_matches hits

        This is "just-in-time" context: instead of loading every note into the
        prompt, the agent asks for the three lines it needs.
        """
        # TODO: implement
        raise NotImplementedError

    def tools(self) -> list[Tool]:
        """Four tools, in this order: write_note, read_note, list_notes, grep_notes.

        Define small inner functions with model-facing docstrings that call the
        methods above, and `build_tool` each one:
            write_note(name: str, content: str, append: bool = False) -> str
            read_note(name: str, offset: int = 0) -> str
            list_notes() -> str        "\\n".join(...) or "(workspace is empty)"
            grep_notes(pattern: str) -> str   "\\n".join(...) or "(no matches)"

        Return text, not lists: "a.md\\nb.md" reads better to a model than a JSON
        array. And say "(no matches)" out loud — an empty string looks like a
        broken tool.
        """
        # TODO: implement
        raise NotImplementedError


def offload_large_output(text: str, workspace: Workspace, limit: int = 2000, *,
                         preview_chars: int = 500, prefix: str = "output") -> str:
    """Keep big tool results OUT of the context window.

    Spec:
      * len(text) <= limit -> return text unchanged, write nothing
      * prefix must match PREFIX -> else ValueError
      * pick the first free name f"outputs/{prefix}-{n:03d}.txt" for n = 1, 2, ...
        (never overwrite an earlier output — the model may still want it)
      * write the FULL text there (bypass max_note_chars: this is the escape hatch
        for big things)
      * return exactly:

        [output too large: {len(text):,} chars, {lines:,} lines. Full text saved to {name}]
        --- first {preview_chars} chars ---
        {text[:preview_chars]}
        --- end of preview ---
        Use read_note({name!r}, offset=...) or grep_notes(pattern) to see more.

        where lines = text.count("\\n") + 1

    A 50k-char result costs ~12k tokens on EVERY later call if it stays in the
    conversation. The pointer costs ~150.
    """
    # TODO: implement
    raise NotImplementedError


def offloading_tool(tool: Tool, workspace: Workspace, limit: int = 2000, *,
                    preview_chars: int = 500) -> Tool:
    """Return a NEW Tool with the same name, description and parameters, whose func:

      1. calls the original `tool.func(**kwargs)` (let exceptions propagate —
         the outer Tool.call handles them exactly as before)
      2. turns a non-str result into text with json.dumps(value, default=str)
      3. returns offload_large_output(text, workspace, limit,
                                      preview_chars=preview_chars, prefix=tool.name)

    One wrapper, and every tool in your registry is safe from flooding the window.
    """
    # TODO: implement
    raise NotImplementedError
