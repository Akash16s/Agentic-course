"""EXERCISE 1 — Permissions.

The control that actually works. Detection is telemetry; this is the fire door.

    pytest chapters/ch14_security/tests -q -k permissions
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from agentlib import errors


class Decision(str, Enum):
    """ALLOW, ASK, DENY — values are the lowercase names."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionDenied(errors.LLMError):
    """A tool call refused by policy. Not retryable."""

    retryable = False


@dataclass
class Rule:
    """pattern: str (a glob over tool names), decision: Decision,
       when: Callable[[dict], bool] | None = None"""

    pattern: str
    decision: Decision
    when: Callable[[dict[str, Any]], bool] | None = None

    def matches(self, tool: str, arguments: dict[str, Any]) -> bool:
        """`fnmatch` the tool name, then the `when` predicate if there is one.

        A PREDICATE THAT RAISES MUST RETURN FALSE, not propagate. A buggy predicate
        should fail to match — i.e. fall through to the next rule and ultimately to
        the default deny. Letting it raise would take the agent down; letting it
        pass would be worse.
        """
        # TODO: implement
        raise NotImplementedError


class PermissionPolicy:
    """Decide whether a tool call is allowed, refused, or needs a human.

    __init__(self, rules: list[Rule] | None = None, *, default=Decision.DENY)

    DEFAULT DENY. With default-allow, every tool anyone adds later is live in
    production the moment it is registered — including the one written in a hurry
    on a Friday afternoon.
    """

    def __init__(self, rules: list[Rule] | None = None,
                 *, default: Decision = Decision.DENY) -> None:
        # TODO: implement
        raise NotImplementedError

    def allow(self, pattern: str, **kwargs: Any) -> "PermissionPolicy":
        """Append an ALLOW rule (kwargs may carry `when=`). Return self to chain."""
        # TODO: implement
        raise NotImplementedError

    def ask(self, pattern: str, **kwargs: Any) -> "PermissionPolicy":
        # TODO: implement
        raise NotImplementedError

    def deny(self, pattern: str, **kwargs: Any) -> "PermissionPolicy":
        # TODO: implement
        raise NotImplementedError

    def decide(self, tool: str, arguments: dict[str, Any] | None = None) -> Decision:
        """FIRST MATCHING RULE WINS; no match -> self.default.

        First-match-wins is what makes "everything under read_*, except secrets"
        expressible: put the specific deny BEFORE the broad allow. Last-match-wins
        would work too, but you must pick one and the tests here assume first.
        """
        # TODO: implement
        raise NotImplementedError


class GuardedRegistry:
    """Wrap a ToolRegistry and enforce a policy.

    __init__(self, inner, policy, *, approve: Callable[[str, dict], bool] | None)

    execute(name, arguments):
      * parse arguments to a dict (non-dict -> {} for the decision; pass the
        ORIGINAL through to inner.execute so the registry can report bad JSON)
      * DENY -> record in self.denied and return
            ToolResult(f"permission denied: {name!r} is not allowed in this context",
                       is_error=True)
      * ASK  -> no approver, or approve(...) is falsy -> record and return
            ToolResult(f"permission denied: a human declined {name!r}", is_error=True)
      * otherwise -> inner.execute(name, arguments)

    A DENIAL IS A TOOL RESULT, NOT AN EXCEPTION. The model should see it and route
    around it, exactly like any other tool failure from Chapter 2. Raising kills
    the run, tells the user nothing, and throws away the trace.

    `__getattr__` delegates, so this stays a drop-in for ToolRegistry.
    """

    def __init__(self, inner: Any, policy: PermissionPolicy,
                 *, approve: Callable[[str, dict[str, Any]], bool] | None = None) -> None:
        # TODO: implement (also: self.denied = [])
        raise NotImplementedError

    def execute(self, name: str, arguments: Any) -> Any:
        # TODO: implement
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        # TODO: implement
        raise NotImplementedError
