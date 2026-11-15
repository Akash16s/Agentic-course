"""SOLUTION — Chapter 13b, Exercise 1."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from agentlib import errors
from agentlib.hardening import CircuitBreaker, CircuitOpen
from agentlib.llm import LLMResponse, Message
from agentlib.retry import chat_with_retry


@dataclass
class Attempt:
    """One model's turn in a fallback chain."""

    model: str                              # the NAME from the chain, not response.model
    ok: bool = False
    error: errors.LLMError | None = None
    skipped: bool = False                   # breaker open: never called at all


class AllModelsFailed(errors.LLMError):
    """Every model in the chain failed (or was skipped). Carries every attempt."""

    retryable = False

    def __init__(self, attempts: list[Attempt]) -> None:
        parts = []
        for a in attempts:
            what = "skipped (breaker open)" if a.skipped else repr(a.error)
            parts.append(f"{a.model}: {what}")
        super().__init__("all models failed -> " + "; ".join(parts))
        self.attempts = attempts

    @property
    def errors(self) -> list[errors.LLMError]:
        return [a.error for a in self.attempts if a.error is not None]


class FallbackClient:
    """Try models in order. Fall through on THEIR problems, stop on YOURS."""

    def __init__(
        self,
        clients: list[tuple[str, Any]],
        *,
        breakers: dict[str, CircuitBreaker] | None = None,
        attempts_per_model: int = 1,
        base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not clients:
            raise ValueError("a fallback chain needs at least one client")
        names = [name for name, _ in clients]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate model names in chain: {names}")
        self.clients = list(clients)
        self.breakers = dict(breakers or {})
        self.attempts_per_model = attempts_per_model
        self.base_delay = base_delay
        self.sleep = sleep
        self.last_attempts: list[Attempt] = []
        self.answered_by: str | None = None
        self.served_by: Counter[str] = Counter()

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        attempts: list[Attempt] = []
        self.last_attempts = attempts
        self.answered_by = None

        for name, client in self.clients:
            breaker = self.breakers.get(name)
            if breaker is not None and not breaker.allow():
                attempts.append(Attempt(
                    model=name, skipped=True,
                    error=CircuitOpen(f"{name}: circuit open, skipped")))
                continue
            try:
                response = chat_with_retry(
                    client, messages,
                    max_attempts=self.attempts_per_model,
                    base_delay=self.base_delay,
                    sleep=self.sleep,
                    **kwargs,
                )
            except errors.LLMError as exc:
                attempts.append(Attempt(model=name, error=exc))
                if not exc.retryable:
                    # your bug, not their outage: do not blame the breaker either
                    raise
                if breaker is not None:
                    breaker.record_failure()
                continue
            if breaker is not None:
                breaker.record_success()
            attempts.append(Attempt(model=name, ok=True))
            self.answered_by = name
            self.served_by[name] += 1
            return response

        raise AllModelsFailed(attempts)
