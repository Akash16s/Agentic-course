"""SOLUTION — Chapter 8, Exercise 2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Route:
    name: str
    description: str
    when_not: str = ""   # the single most effective field in this dataclass


class Router:
    """Pick one specialist for a request.

    The cheapest useful multi-agent pattern, and often the only one you need: one
    small model decides which prompt+toolset handles the request, and nothing else
    about the system is distributed.
    """

    def __init__(self, routes: list[Route], *, default: str | None = None) -> None:
        if not routes:
            raise ValueError("a router needs at least one route")
        self.routes = {r.name: r for r in routes}
        self.default = default or routes[0].name

    def prompt(self, query: str) -> str:
        lines = ["Route this request to exactly one handler.\n"]
        for route in self.routes.values():
            lines.append(f"- {route.name}: {route.description}")
            if route.when_not:
                lines.append(f"    do NOT use for: {route.when_not}")
        lines.append(f"\nREQUEST: {query}")
        lines.append("\nReply with the handler name and nothing else.")
        return "\n".join(lines)

    def parse(self, raw: str) -> str:
        """Map a model's answer to a route name. Unrecognised -> the default.

        Matches case-insensitively and accepts the name embedded in a sentence,
        because models say "I'd route this to billing" about a third of the time
        however firmly you ask for one word.
        """
        text = (raw or "").strip().lower()
        for name in self.routes:
            if name.lower() == text:
                return name
        for name in self.routes:
            if name.lower() in text:
                return name
        return self.default

    def route(self, query: str, call_model: Callable[[str], str]) -> str:
        return self.parse(call_model(self.prompt(query)))
