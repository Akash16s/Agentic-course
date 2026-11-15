"""EXERCISE 3 — Retry with exponential backoff and jitter.

WHY: Model APIs fail. Constantly. 429s when you are over your rate limit, 529/503 when
the provider is overloaded, timeouts when a long generation stalls. An agent that dies
on the first 429 is a toy. An agent that retries a 400 forever is worse than a toy.

THE TWO RULES:

  1. **Retry only what can succeed.** 429 and 5xx and timeouts: yes. 400 and 401: never
     — the same bytes will fail the same way, you just fail slower.
  2. **Randomise your delays.** If a thousand workers all hit a 429 at once and all
     back off exactly 1s, 2s, 4s, they come back in synchronised waves and re-trigger
     the limit forever. This is the "thundering herd". Jitter breaks it up.

Note the injected `sleep` and `rng` parameters. That is not over-engineering — it is
what makes this function testable in microseconds instead of minutes. Dependency
injection for time is a habit worth forming.

Run the tests:
    pytest chapters/ch01_agent_loop/tests -q -k retry
"""

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
    """How long to wait before retry number `attempt` (1-based: attempt=1 is the wait
    after the FIRST failure).

    Spec:
        raw   = base_delay * (2 ** (attempt - 1))
        raw   = min(raw, max_delay)
        if jitter:  return raw * (0.5 + 0.5 * rng())     # "equal jitter"
        else:       return raw

    So with base_delay=1 and no jitter: 1, 2, 4, 8, 16, 30, 30, ...
    With jitter, each of those becomes a random value in [half, full].

    >>> backoff_delay(1, jitter=False)
    1.0
    >>> backoff_delay(4, jitter=False)
    8.0
    >>> backoff_delay(10, jitter=False)
    30.0
    """
    # TODO: implement
    raise NotImplementedError


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
    """Call `client.chat(messages, **chat_kwargs)`, retrying transient failures.

    Spec:
      * `max_attempts` is the TOTAL number of calls, not the number of retries.
        max_attempts=3 means: try, retry, retry, then give up.
      * On success: return the LLMResponse immediately.
      * On an `errors.LLMError` with `.retryable` False: re-raise at once. No sleep.
      * On a retryable error:
          - if this was the last allowed attempt, re-raise
          - otherwise compute `backoff_delay(attempt, ...)`, call
            `on_retry(attempt, exc, delay)` if provided, `sleep(delay)`, and try again
      * Non-LLMError exceptions propagate untouched. Do not swallow bugs in your own
        code by treating every exception as a network blip.

    `on_retry` exists so Chapter 12 can hang logging and tracing off it without this
    function knowing anything about logging.
    """
    # TODO: implement
    raise NotImplementedError
