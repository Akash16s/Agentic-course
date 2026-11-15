"""SOLUTION — Chapter 14, Exercise 1."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from agentlib import errors


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionDenied(errors.LLMError):
    """A tool call was refused by policy."""

    retryable = False


@dataclass
class Rule:
    """A glob over tool names, plus optional argument predicates."""

    pattern: str
    decision: Decision
    when: Callable[[dict[str, Any]], bool] | None = None

    def matches(self, tool: str, arguments: dict[str, Any]) -> bool:
        if not fnmatch.fnmatch(tool, self.pattern):
            return False
        if self.when is None:
            return True
        try:
            return bool(self.when(arguments))
        except Exception:  # noqa: BLE001 - a broken predicate must not silently allow
            return False


class PermissionPolicy:
    """Decide whether a tool call is allowed, refused, or needs a human.

    DEFAULT DENY. An agent should be able to do exactly what you listed and nothing
    else. Default-allow means every tool you add later is live in production the
    moment it is registered, including the one someone wrote in a hurry.

    Rules are evaluated IN ORDER; the first match wins. That makes
    "allow read_*, but deny read_secrets" expressible — put the specific rule first.
    """

    def __init__(self, rules: list[Rule] | None = None,
                 *, default: Decision = Decision.DENY) -> None:
        self.rules = list(rules or [])
        self.default = default

    def allow(self, pattern: str, **kwargs: Any) -> "PermissionPolicy":
        self.rules.append(Rule(pattern, Decision.ALLOW, kwargs.get("when")))
        return self

    def ask(self, pattern: str, **kwargs: Any) -> "PermissionPolicy":
        self.rules.append(Rule(pattern, Decision.ASK, kwargs.get("when")))
        return self

    def deny(self, pattern: str, **kwargs: Any) -> "PermissionPolicy":
        self.rules.append(Rule(pattern, Decision.DENY, kwargs.get("when")))
        return self

    def decide(self, tool: str, arguments: dict[str, Any] | None = None) -> Decision:
        arguments = arguments or {}
        for rule in self.rules:
            if rule.matches(tool, arguments):
                return rule.decision
        return self.default


class GuardedRegistry:
    """Wraps a ToolRegistry and enforces a policy.

    `approve(tool, arguments) -> bool` is called for ASK decisions. In a CLI that
    is a prompt; in a web app it is a queued approval; in tests it is a lambda.
    """

    def __init__(self, inner: Any, policy: PermissionPolicy,
                 *, approve: Callable[[str, dict[str, Any]], bool] | None = None) -> None:
        self.inner = inner
        self.policy = policy
        self.approve = approve
        self.denied: list[tuple[str, dict[str, Any]]] = []

    def execute(self, name: str, arguments: Any) -> Any:
        from agentlib.tools import ToolResult

        parsed = arguments if isinstance(arguments, dict) else {}
        decision = self.policy.decide(name, parsed)

        if decision is Decision.DENY:
            self.denied.append((name, parsed))
            # a refusal is a TOOL RESULT, not an exception: the model should see it
            # and route around it, exactly like any other tool failure
            return ToolResult(
                f"permission denied: {name!r} is not allowed in this context",
                is_error=True,
            )

        if decision is Decision.ASK:
            if self.approve is None or not self.approve(name, parsed):
                self.denied.append((name, parsed))
                return ToolResult(
                    f"permission denied: a human declined {name!r}", is_error=True
                )

        return self.inner.execute(name, arguments)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)
