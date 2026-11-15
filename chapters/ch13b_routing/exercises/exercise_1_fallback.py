"""EXERCISE 1 — The fallback chain.

    pytest chapters/ch13b_routing/tests -q -k fallback
"""

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
    """One model's turn in a fallback chain. (Given — nothing to do here.)"""

    model: str                              # the NAME from the chain, not response.model
    ok: bool = False
    error: errors.LLMError | None = None
    skipped: bool = False                   # breaker open: never called at all


class AllModelsFailed(errors.LLMError):
    """Every model in the chain failed (or was skipped). Carries every attempt.
    (Given — nothing to do here.)

    Not retryable: the chain WAS the retry. An outer retry around a whole chain
    multiplies your traffic by the chain length during exactly the moment every
    provider is struggling.
    """

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
    """Try models in order. Fall through on THEIR problems, stop on YOURS.

        client = FallbackClient([
            ("sonnet", LLMClient("anthropic/claude-sonnet-4.5")),
            ("gpt-4o", LLMClient("openai/gpt-4o")),
        ])
        client.chat(messages)            # same interface as LLMClient

    __init__(self, clients: list[tuple[name, client]], *,
             breakers: dict[name, CircuitBreaker] | None = None,
             attempts_per_model: int = 1,
             base_delay: float = 0.5,
             sleep: Callable[[float], None] = time.sleep)
    """

    def __init__(
        self,
        clients: list[tuple[str, Any]],
        *,
        breakers: dict[str, CircuitBreaker] | None = None,
        attempts_per_model: int = 1,
        base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Store everything. Validate:
          * an empty `clients` list -> ValueError
          * duplicate names         -> ValueError (the attempt log would be
                                       ambiguous, and so would your metrics)

        Also keep three pieces of observability state:
          self.last_attempts: list[Attempt]  — the log of the most recent chat()
          self.answered_by:   str | None     — name that answered the last chat()
          self.served_by:     Counter[str]   — lifetime answers per name

        `served_by` is the number you will actually look at in production. If
        your primary model answers 99% of traffic on Monday and 60% on Tuesday,
        something happened on Tuesday and nobody's alert fired, because every
        request still succeeded.
        """
        # TODO: implement
        raise NotImplementedError

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Try each (name, client) in order. Spec:

          0. reset: self.last_attempts = a NEW empty list, self.answered_by = None

          for each (name, client):
          1. breaker = self.breakers.get(name). If it exists and NOT allow():
             append Attempt(name, skipped=True, error=CircuitOpen(...)) and move on
             WITHOUT calling the client. That is the breaker's whole job.
          2. call it via agentlib.retry.chat_with_retry(client, messages,
             max_attempts=self.attempts_per_model, base_delay=self.base_delay,
             sleep=self.sleep, **kwargs). RETRY FIRST, THEN FALL BACK: a single
             429 blip should not move you off your primary model.
          3. it raised an errors.LLMError:
               - append Attempt(name, error=exc)
               - NOT exc.retryable (400, 401, 404...) -> RE-RAISE IT, now.
                 A malformed request fails identically on every model; a bad key
                 is your bug. Falling back just hides it behind N slow failures.
                 Do not touch the breaker: the provider is healthy, you are not.
               - retryable -> breaker.record_failure() (if any), next model
          4. success: breaker.record_success() (if any), append
             Attempt(name, ok=True), set answered_by, bump served_by[name],
             return the response UNCHANGED.

          5. ran out of models -> raise AllModelsFailed(attempts)

        Anything that is NOT an LLMError (a ValueError, a KeyError) is a bug in
        your code. Let it propagate — never catch-all here.
        """
        # TODO: implement
        raise NotImplementedError
