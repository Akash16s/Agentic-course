"""SOLUTION — Chapter 2, Exercise 4."""

from __future__ import annotations

import json
from typing import Any, Callable

from .exercise_3_build_tool import Tool, ToolResult, build_tool


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}   # dicts keep insertion order
        for t in tools or []:
            self.register(t)

    def register(self, t: Tool | Callable[..., Any]) -> Tool:
        if not isinstance(t, Tool):
            t = build_tool(t)
        if t.name in self._tools:
            raise ValueError(f"tool {t.name!r} is already registered")
        self._tools[t.name] = t
        return t

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any] | str) -> ToolResult:
        t = self._tools.get(name)
        if t is None:
            return ToolResult(
                f"unknown tool {name!r}. Available: {', '.join(self.names) or 'none'}",
                is_error=True,
            )
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as exc:
                return ToolResult(f"arguments were not valid JSON: {exc}", is_error=True)
        if not isinstance(arguments, dict):
            return ToolResult("arguments must be a JSON object", is_error=True)
        return t.call(arguments)
