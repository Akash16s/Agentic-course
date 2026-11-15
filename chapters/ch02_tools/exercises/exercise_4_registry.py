"""EXERCISE 4 — The tool registry.

WHY: Somewhere there has to be a dict from name to function, and a dispatcher that
never lets a tool's failure become your agent's failure. This is that.

    pytest chapters/ch02_tools/tests -q -k registry
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .exercise_3_build_tool import Tool, ToolResult, build_tool


class ToolRegistry:
    """The set of tools an agent may use, plus safe dispatch.

    >>> r = ToolRegistry()
    >>> _ = r.register(lambda: None)   # plain functions are wrapped automatically
    """

    def __init__(self, tools: list[Tool] | None = None) -> None:
        """Store an ordered name -> Tool mapping and register anything passed in."""
        # TODO: implement
        raise NotImplementedError

    def register(self, t: Tool | Callable[..., Any]) -> Tool:
        """Add a tool. Accepts a `Tool` OR a plain function (wrap it with build_tool).

        Raise ValueError on a duplicate name. Silently overwriting is how you end up
        with an agent calling the wrong `search`, and it is very hard to see.

        Return the registered Tool.
        """
        # TODO: implement
        raise NotImplementedError

    def __contains__(self, name: object) -> bool:
        # TODO: implement
        raise NotImplementedError

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

    def get(self, name: str) -> Tool | None:
        """The Tool, or None. Do not raise — callers check."""
        # TODO: implement
        raise NotImplementedError

    @property
    def names(self) -> list[str]:
        """Registered names, in registration order."""
        # TODO: implement
        raise NotImplementedError

    def specs(self) -> list[dict[str, Any]]:
        """The whole `tools=[...]` argument for the API call."""
        # TODO: implement
        raise NotImplementedError

    def execute(self, name: str, arguments: dict[str, Any] | str) -> ToolResult:
        """Run one tool by name. MUST NOT RAISE.

        Spec, in order:
          1. name not registered -> ToolResult(
                 f"unknown tool {name!r}. Available: {', '.join(self.names) or 'none'}",
                 is_error=True)
             Listing the real names matters: the model reads this and corrects itself.
          2. `arguments` is a str -> json.loads it.
                 empty/whitespace  -> treat as {}
                 JSONDecodeError   -> ToolResult(
                     f"arguments were not valid JSON: {exc}", is_error=True)
          3. still not a dict (e.g. the model sent `[1,2]`) ->
                 ToolResult("arguments must be a JSON object", is_error=True)
          4. otherwise -> tool.call(arguments)
        """
        # TODO: implement
        raise NotImplementedError
