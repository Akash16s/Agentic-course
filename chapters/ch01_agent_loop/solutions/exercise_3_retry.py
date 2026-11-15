"""SOLUTION — Exercise 3."""

from __future__ import annotations

import random
import time
from typing import Any, Callable

from agentlib import errors
from agentlib.llm import LLMResponse, Message


def backoff_delay(
    attempt: int,
    *,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    rng: Callable[[], float] = random.random,
) -> float:
    raw = min(base_delay * (2 ** (attempt - 1)), max_delay)
    if jitter:
        # "equal jitter": half fixed, half random. Keeps the exponential shape while
        # spreading a herd of clients out over a window.
        return raw * (0.5 + 0.5 * rng())
    return raw


def chat_with_retry(
    client: Any,
    messages: list[Message],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
    on_retry: Callable[[int, errors.LLMError, float], None] | None = None,
    **chat_kwargs: Any,
) -> LLMResponse:
    for attempt in range(1, max_attempts + 1):
        try:
            return client.chat(messages, **chat_kwargs)
        except errors.LLMError as exc:
            # Two ways to stop: the error can never succeed, or we are out of attempts.
            if not exc.retryable or attempt == max_attempts:
                raise
            delay = backoff_delay(
                attempt,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=jitter,
                rng=rng,
            )
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
        # Anything that is not an LLMError propagates: it is a bug in our code, and
        # retrying a bug just makes it slower and harder to see.

    raise AssertionError("unreachable: the loop always returns or raises")
