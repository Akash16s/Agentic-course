"""SOLUTION — Chapter 8b, Exercise 4."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agentlib.security import sandbox_path
from agentlib.tools import Tool, build_tool

PREFIX = re.compile(r"^[A-Za-z0-9_-]+$")


class Workspace:
    def __init__(self, root: str | Path, *, max_read_chars: int = 4000,
                 max_note_chars: int = 100_000) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_read_chars = max_read_chars
        self.max_note_chars = max_note_chars

    def path(self, name: str) -> Path:
        target = sandbox_path(self.root, name)
        if target == self.root.resolve():
            raise ValueError("a note name must be a file path, not the workspace root")
        return target

    def write_note(self, name: str, content: str, append: bool = False) -> str:
        if len(content) > self.max_note_chars:
            raise ValueError(
                f"note is {len(content)} chars; the limit is {self.max_note_chars}"
            )
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a" if append else "w", encoding="utf-8") as f:
            f.write(content)
        return f"{'appended' if append else 'wrote'} {len(content)} chars to {name}"

    def read_note(self, name: str, offset: int = 0, limit: int | None = None) -> str:
        target = self.path(name)
        if not target.is_file():
            raise FileNotFoundError(f"no note named {name!r}")
        text = target.read_text(encoding="utf-8")
        limit = self.max_read_chars if limit is None else min(limit, self.max_read_chars)
        offset = max(0, offset)
        chunk = text[offset: offset + limit]
        end = offset + len(chunk)
        if end < len(text):
            chunk += (f"\n...[showing chars {offset}-{end} of {len(text)}; "
                      f"call read_note with offset={end} to continue]")
        return chunk

    def list_notes(self) -> list[str]:
        root = self.root.resolve()
        return sorted(
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        )

    def grep_notes(self, pattern: str, *, ignore_case: bool = True,
                   max_matches: int = 50) -> list[str]:
        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            raise ValueError(f"invalid pattern {pattern!r}: {exc}") from None
        out: list[str] = []
        for name in self.list_notes():
            text = (self.root.resolve() / name).read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    out.append(f"{name}:{lineno}: {line.strip()[:200]}")
                    if len(out) >= max_matches:
                        return out
        return out

    def tools(self) -> list[Tool]:
        def write_note(name: str, content: str, append: bool = False) -> str:
            """Save text to a file in your workspace (notes, plans, findings).

            Args:
                name: relative path such as notes/findings.md
                content: the text to write
                append: add to the end instead of replacing the file
            """
            return self.write_note(name, content, append)

        def read_note(name: str, offset: int = 0) -> str:
            """Read a file from your workspace, a chunk at a time.

            Args:
                name: relative path of the file
                offset: character to start from, for reading long files in pieces
            """
            return self.read_note(name, offset)

        def list_notes() -> str:
            """List every file in your workspace."""
            return "\n".join(self.list_notes()) or "(workspace is empty)"

        def grep_notes(pattern: str) -> str:
            """Search every workspace file for a regex. Returns file:line: text.

            Args:
                pattern: a regular expression, matched case-insensitively
            """
            return "\n".join(self.grep_notes(pattern)) or "(no matches)"

        return [build_tool(f) for f in (write_note, read_note, list_notes, grep_notes)]


def offload_large_output(text: str, workspace: Workspace, limit: int = 2000, *,
                         preview_chars: int = 500, prefix: str = "output") -> str:
    if len(text) <= limit:
        return text
    if not PREFIX.match(prefix):
        raise ValueError(f"bad prefix {prefix!r}")
    n = 1
    while workspace.path(f"outputs/{prefix}-{n:03d}.txt").exists():
        n += 1
    name = f"outputs/{prefix}-{n:03d}.txt"
    target = workspace.path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    lines = text.count("\n") + 1
    return (
        f"[output too large: {len(text):,} chars, {lines:,} lines. "
        f"Full text saved to {name}]\n"
        f"--- first {preview_chars} chars ---\n"
        f"{text[:preview_chars]}\n"
        f"--- end of preview ---\n"
        f"Use read_note({name!r}, offset=...) or grep_notes(pattern) to see more."
    )


def offloading_tool(tool: Tool, workspace: Workspace, limit: int = 2000, *,
                    preview_chars: int = 500) -> Tool:
    def run(**kwargs: Any) -> str:
        value = tool.func(**kwargs)
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        return offload_large_output(text, workspace, limit,
                                    preview_chars=preview_chars, prefix=tool.name)

    return Tool(name=tool.name, description=tool.description,
                parameters=tool.parameters, func=run)
