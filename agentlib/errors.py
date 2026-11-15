"""Our own error hierarchy.

Why not just let the `openai` SDK's exceptions bubble up? Two reasons:

1. **Provider independence.** Chapter 17 will run this same code against a different
   client. Retry logic that catches `openai.RateLimitError` is welded to one SDK.
2. **Testability.** SDK exceptions need real `httpx.Response` objects to construct, which
   makes writing a fake client miserable. Ours take a string.

Everything in `agentlib` raises these. `LLMClient` translates the SDK's exceptions at the
boundary — the classic "adapter" move: foreign errors get converted once, at the edge.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for everything that can go wrong talking to a model."""

    #: Does retrying this exact request have any chance of working?
    retryable: bool = False

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:  # nicer pytest output
        return f"{type(self).__name__}({self.message!r}, status_code={self.status_code})"


class RateLimitError(LLMError):
    """HTTP 429. You are going too fast, or you are out of credit.

    Retryable — but back off, and respect `Retry-After` if the provider sent one.
    """

    retryable = True


class ServerError(LLMError):
    """HTTP 5xx. Their problem, not yours. Retryable."""

    retryable = True


class TimeoutError(LLMError):  # noqa: A001 - shadowing the builtin is intentional here
    """The request took longer than our timeout. Usually retryable."""

    retryable = True


class ConnectionError(LLMError):  # noqa: A001
    """Network never reached them. Retryable."""

    retryable = True


class BadRequestError(LLMError):
    """HTTP 400/404/422. YOUR request is malformed — bad model id, bad schema, too many
    tokens. Retrying identical bytes gives an identical failure. NOT retryable."""

    retryable = False


class AuthError(LLMError):
    """HTTP 401/403. Bad or missing key. Not retryable, and no amount of waiting helps."""

    retryable = False


def classify_status(status_code: int, message: str = "") -> LLMError:
    """Map an HTTP status code to one of our errors.

    Used by `LLMClient`, and handy in tests. Note the ordering: 429 is a 4xx but must be
    checked *before* the generic 4xx branch, because it is the one client error that IS
    worth retrying.
    """
    if status_code == 429:
        return RateLimitError(message or "rate limited", status_code=429)
    if status_code in (401, 403):
        return AuthError(message or "authentication failed", status_code=status_code)
    if 500 <= status_code < 600:
        return ServerError(message or "server error", status_code=status_code)
    if 400 <= status_code < 500:
        return BadRequestError(message or "bad request", status_code=status_code)
    return LLMError(message or f"unexpected status {status_code}", status_code=status_code)


class BudgetExceeded(LLMError):
    """Your own spend limit was hit. Not an API error at all — a guard YOU installed.

    An agent that can loop is an agent that can spend. Chapter 13 makes this a hard
    circuit breaker; Chapter 1 just makes it visible.
    """

    retryable = False

    def __init__(self, spent: float, budget: float) -> None:
        super().__init__(f"budget exceeded: spent ${spent:.4f} of ${budget:.4f} limit")
        self.spent = spent
        self.budget = budget


class StopSignal(Exception):
    """Raise inside a tool to end an agent run successfully.

    NOT an LLMError — it is control flow, not a failure. `Tool.call` re-raises it
    instead of turning it into an error result, which is the one exception to
    "tool failures are data".

    Use it for an explicit `submit_answer(text)` tool. Relying on the model to simply
    stop calling tools works most of the time; an explicit terminator works every time.
    """

    def __init__(self, output: str = "") -> None:
        super().__init__(output)
        self.output = output
