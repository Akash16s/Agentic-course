"""Tests for Exercise 3 — retry with backoff. No real sleeping, no real network."""

import pytest

from agentlib import errors
from agentlib.llm import LLMResponse, Usage
from agentlib.testing import FakeLLMClient
from chapters.ch01_agent_loop.exercises.exercise_3_retry import (
    backoff_delay,
    chat_with_retry,
)

MSGS = [{"role": "user", "content": "hi"}]


class Clock:
    """Records sleeps instead of performing them."""

    def __init__(self):
        self.slept: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)


class TestBackoffDelay:
    def test_doubles_each_attempt(self):
        assert backoff_delay(1, jitter=False) == 1.0
        assert backoff_delay(2, jitter=False) == 2.0
        assert backoff_delay(3, jitter=False) == 4.0
        assert backoff_delay(4, jitter=False) == 8.0

    def test_respects_base_delay(self):
        assert backoff_delay(1, base_delay=0.5, jitter=False) == 0.5
        assert backoff_delay(3, base_delay=0.5, jitter=False) == 2.0

    def test_caps_at_max_delay(self):
        assert backoff_delay(20, jitter=False) == 30.0
        assert backoff_delay(20, max_delay=5.0, jitter=False) == 5.0

    def test_jitter_lands_between_half_and_full(self):
        assert backoff_delay(3, jitter=True, rng=lambda: 0.0) == 2.0   # 4 * 0.5
        assert backoff_delay(3, jitter=True, rng=lambda: 1.0) == 4.0   # 4 * 1.0

    def test_jitter_actually_varies(self):
        seen = {backoff_delay(3) for _ in range(50)}
        assert len(seen) > 5, "jitter must randomise, or you get a thundering herd"


class TestChatWithRetry:
    def test_returns_immediately_on_success(self):
        client = FakeLLMClient(["ok"])
        clock = Clock()
        r = chat_with_retry(client, MSGS, sleep=clock)
        assert r.text == "ok"
        assert client.call_count == 1
        assert clock.slept == [], "no sleeping on the happy path"

    def test_retries_a_rate_limit_then_succeeds(self):
        client = FakeLLMClient([errors.RateLimitError("429"), "recovered"])
        clock = Clock()
        r = chat_with_retry(client, MSGS, sleep=clock, jitter=False)
        assert r.text == "recovered"
        assert client.call_count == 2
        assert clock.slept == [1.0]

    def test_retries_a_server_error(self):
        client = FakeLLMClient(
            [errors.ServerError("503"), errors.ServerError("503"), "third time lucky"]
        )
        clock = Clock()
        r = chat_with_retry(client, MSGS, sleep=clock, jitter=False)
        assert r.text == "third time lucky"
        assert clock.slept == [1.0, 2.0], "delays must grow exponentially"

    def test_gives_up_after_max_attempts(self):
        client = FakeLLMClient([errors.RateLimitError("429")] * 5)
        clock = Clock()
        with pytest.raises(errors.RateLimitError):
            chat_with_retry(client, MSGS, max_attempts=3, sleep=clock, jitter=False)
        assert client.call_count == 3, "max_attempts is TOTAL calls, not extra retries"
        assert len(clock.slept) == 2, "no sleep after the final failure"

    def test_does_not_retry_a_bad_request(self):
        client = FakeLLMClient([errors.BadRequestError("bad model id"), "unreachable"])
        clock = Clock()
        with pytest.raises(errors.BadRequestError):
            chat_with_retry(client, MSGS, sleep=clock)
        assert client.call_count == 1, "a 400 will fail identically forever"
        assert clock.slept == []

    def test_does_not_retry_an_auth_error(self):
        client = FakeLLMClient([errors.AuthError("401")])
        with pytest.raises(errors.AuthError):
            chat_with_retry(client, MSGS, sleep=Clock())
        assert client.call_count == 1

    def test_non_llm_exceptions_propagate_untouched(self):
        client = FakeLLMClient([ValueError("a bug in your own code")])
        with pytest.raises(ValueError):
            chat_with_retry(client, MSGS, sleep=Clock())
        assert client.call_count == 1, "never mask your own bugs as network blips"

    def test_passes_kwargs_through_to_chat(self):
        client = FakeLLMClient(["ok"])
        chat_with_retry(client, MSGS, sleep=Clock(), temperature=0.7, max_tokens=50)
        _, kwargs = client.calls[0]
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 50
        assert "sleep" not in kwargs and "max_attempts" not in kwargs, (
            "retry's own options must not leak into the API request"
        )

    def test_on_retry_callback(self):
        seen = []
        client = FakeLLMClient([errors.ServerError("500"), "ok"])
        chat_with_retry(
            client,
            MSGS,
            sleep=Clock(),
            jitter=False,
            on_retry=lambda attempt, exc, delay: seen.append((attempt, type(exc), delay)),
        )
        assert seen == [(1, errors.ServerError, 1.0)]

    def test_max_delay_is_honoured_across_attempts(self):
        client = FakeLLMClient([errors.ServerError("500")] * 6)
        clock = Clock()
        with pytest.raises(errors.ServerError):
            chat_with_retry(
                client, MSGS, max_attempts=6, sleep=clock, jitter=False, max_delay=3.0
            )
        assert clock.slept == [1.0, 2.0, 3.0, 3.0, 3.0]
