"""EXERCISE 2 — Routing.

    pytest chapters/ch08_multi_agent/tests -q -k router
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Route:
    """One handler.

    Fields: name: str, description: str, when_not: str = ""

    `when_not` is the highest-value field here. Routers over-route to whichever
    handler sounds most capable, and one line of "do NOT use for X" moves accuracy
    more than three more sentences describing what the handler does.
    """

    name: str
    description: str
    when_not: str = ""


class Router:
    """Pick one specialist for a request. The cheapest multi-agent pattern, and
    often the only one you need."""

    def __init__(self, routes: list[Route], *, default: str | None = None) -> None:
        """Store routes by name; `default` falls back to the FIRST route's name.
        Raise ValueError on an empty route list."""
        # TODO: implement
        raise NotImplementedError

    def prompt(self, query: str) -> str:
        """Build the routing prompt. Must include, for each route, its name and
        description, and its `when_not` line when it has one. End by asking for the
        handler name and nothing else.

        Keep it short — this runs on every request and should use a cheap model.
        """
        # TODO: implement
        raise NotImplementedError

    def parse(self, raw: str) -> str:
        """Map a model's reply to a route name.

        Spec, in order:
          1. exact match on the stripped, lowercased reply
          2. otherwise the first route whose name appears ANYWHERE in the reply
          3. otherwise self.default

        Step 2 is not laziness. You ask for one word and get "I'd route this to
        billing" roughly a third of the time, however firmly you phrase it. Raising
        on that would take down a production router for a cosmetic reason.

        Step 3 means an unroutable request still goes somewhere. A default handler
        that says "I'm not sure, can you clarify?" beats a 500.
        """
        # TODO: implement
        raise NotImplementedError

    def route(self, query: str, call_model: Callable[[str], str]) -> str:
        """prompt -> call_model -> parse."""
        # TODO: implement
        raise NotImplementedError
