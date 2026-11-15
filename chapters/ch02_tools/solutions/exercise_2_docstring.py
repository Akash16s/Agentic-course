"""SOLUTION — Chapter 2, Exercise 2."""

from __future__ import annotations

import re

ARGS_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters)\s*:\s*$", re.IGNORECASE)
ARG_LINE = re.compile(r"^\s*(\*{0,2}\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$")
SECTION_END = re.compile(r"^\s*(Returns|Raises|Yields|Examples?)\s*:\s*$", re.IGNORECASE)


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    if not doc:
        return "", {}

    summary_lines: list[str] = []
    params: dict[str, str] = {}
    in_args = False
    current: str | None = None

    for line in doc.strip().splitlines():
        if ARGS_HEADER.match(line):
            in_args = True
            continue
        if in_args:
            if SECTION_END.match(line):
                break
            match = ARG_LINE.match(line)
            if match:
                current = match.group(1).lstrip("*")
                params[current] = match.group(2).strip()
            elif current and line.strip():
                # a wrapped continuation line
                params[current] += " " + line.strip()
        else:
            summary_lines.append(line)

    return "\n".join(summary_lines).strip(), params
