"""Tests for Chapter 13b, Exercise 1 — the fallback chain."""

import pytest

from agentlib import errors
from agentlib.hardening import BreakerState, CircuitBreaker
from agentlib.llm import LLMResponse
from agentlib.testing import FakeLLMClient
from chapters.ch13b_routing.exercises.exercise_1_fallback import (
    AllModelsFailed,
    FallbackClient,
)

MSGS = [{"role": "user", "content": "hello"}]


def fake(*script, model="fake/model"):
    return FakeLLMClient(list(script), model=model)


def no_sleep(_seconds):
    pass


class TestHappyPath:
    def test_first_model_answers(self):
        a, b = fake("from a"), fake("from b")
        r = FallbackClient([("a", a), ("b", b)]).chat(MSGS)
        assert r.text == "from a"
        assert b.call_count == 0

    def test_returns_the_response_object_unchanged(self):
        original = LLMResponse(text="x", model="real/model")
        r = FallbackClient([("a", fake(original))]).chat(MSGS)
        assert r is original

    def test_messages_and_kwargs_are_forwarded(self):
        a = fake(errors.ServerError("down"))
        b = fake("ok")
        FallbackClient([("a", a), ("b", b)]).chat(MSGS, temperature=0.3, max_tokens=50)
        for client in (a, b):
            sent_messages, sent_kwargs = client.calls[0]
            assert sent_messages == MSGS
            assert sent_kwargs["temperature"] == 0.3
            assert sent_kwargs["max_tokens"] == 50


class TestFallsThroughOnTheirProblems:
    @pytest.mark.parametrize("error", [
        errors.RateLimitError("429", status_code=429),
        errors.ServerError("503", status_code=503),
        errors.TimeoutError("slow"),
        errors.ConnectionError("no route"),
    ])
    def test_retryable_errors_fall_through(self, error):
        a, b = fake(error), fake("from b")
        r = FallbackClient([("a", a), ("b", b)]).chat(MSGS)
        assert r.text == "from b"
        assert a.call_count == 1

    def test_walks_the_whole_chain(self):
        a = fake(errors.ServerError("a down"))
        b = fake(errors.RateLimitError("b busy"))
        c = fake("from c")
        client = FallbackClient([("a", a), ("b", b), ("c", c)])
        assert client.chat(MSGS).text == "from c"


class TestStopsOnYourProblems:
    def test_bad_request_is_re_raised_immediately(self):
        a, b = fake(errors.BadRequestError("bad schema")), fake("from b")
        with pytest.raises(errors.BadRequestError):
            FallbackClient([("a", a), ("b", b)]).chat(MSGS)
        assert b.call_count == 0, "a 400 fails everywhere; do not fall back on it"

    def test_auth_error_is_re_raised_immediately(self):
        a, b = fake(errors.AuthError("bad key")), fake("from b")
        with pytest.raises(errors.AuthError):
            FallbackClient([("a", a), ("b", b)]).chat(MSGS)
        assert b.call_count == 0

    def test_non_retryable_after_a_retryable_still_stops(self):
        a = fake(errors.ServerError("down"))
        b = fake(errors.BadRequestError("context too long"))
        c = fake("from c")
        with pytest.raises(errors.BadRequestError):
            FallbackClient([("a", a), ("b", b), ("c", c)]).chat(MSGS)
        assert c.call_count == 0

    def test_bugs_in_your_code_propagate(self):
        a, b = fake(ValueError("my bug")), fake("from b")
        with pytest.raises(ValueError):
            FallbackClient([("a", a), ("b", b)]).chat(MSGS)
        assert b.call_count == 0


class TestAllFailed:
    def test_raises_all_models_failed(self):
        client = FallbackClient([("a", fake(errors.ServerError("a"))),
                                 ("b", fake(errors.RateLimitError("b")))])
        with pytest.raises(AllModelsFailed):
            client.chat(MSGS)

    def test_carries_every_error_in_order(self):
        e1, e2 = errors.ServerError("a down"), errors.TimeoutError("b slow")
        client = FallbackClient([("a", fake(e1)), ("b", fake(e2))])
        with pytest.raises(AllModelsFailed) as exc:
            client.chat(MSGS)
        assert exc.value.errors == [e1, e2]
        assert [a.model for a in exc.value.attempts] == ["a", "b"]

class TestAttemptLog:
    def test_answered_by_names_the_model(self):
        client = FallbackClient([("a", fake(errors.ServerError("x"))),
                                 ("b", fake("ok"))])
        client.chat(MSGS)
        assert client.answered_by == "b"

    def test_last_attempts_records_each_try(self):
        err = errors.ServerError("x")
        client = FallbackClient([("a", fake(err)), ("b", fake("ok"))])
        client.chat(MSGS)
        log = client.last_attempts
        assert [(a.model, a.ok) for a in log] == [("a", False), ("b", True)]
        assert log[0].error is err
        assert log[1].error is None

    def test_log_is_reset_on_each_call(self):
        a = fake(errors.ServerError("x"), "second time a works")
        client = FallbackClient([("a", a), ("b", fake("ok"))])
        client.chat(MSGS)
        assert len(client.last_attempts) == 2
        client.chat(MSGS)
        assert [x.model for x in client.last_attempts] == ["a"]
        assert client.answered_by == "a"

    def test_log_includes_the_non_retryable_failure(self):
        client = FallbackClient([("a", fake(errors.BadRequestError("x")))])
        with pytest.raises(errors.BadRequestError):
            client.chat(MSGS)
        assert [a.model for a in client.last_attempts] == ["a"]
        assert client.answered_by is None

    def test_served_by_counts_answers_per_model(self):
        a = fake("ok", errors.ServerError("x"), "ok")
        client = FallbackClient([("a", a), ("b", fake())])
        for _ in range(3):
            client.chat(MSGS)
        assert client.served_by["a"] == 2
        assert client.served_by["b"] == 1


class TestRetryFirstThenFallBack:
    def test_retries_the_same_model_before_moving_on(self):
        a = fake(errors.RateLimitError("blip"), "a recovered")
        b = fake("from b")
        client = FallbackClient([("a", a), ("b", b)], attempts_per_model=2,
                                sleep=no_sleep)
        assert client.chat(MSGS).text == "a recovered"
        assert a.call_count == 2
        assert b.call_count == 0

    def test_falls_back_once_retries_are_exhausted(self):
        a = fake(errors.ServerError("1"), errors.ServerError("2"))
        b = fake("from b")
        client = FallbackClient([("a", a), ("b", b)], attempts_per_model=2,
                                sleep=no_sleep)
        assert client.chat(MSGS).text == "from b"
        assert a.call_count == 2

    def test_does_not_retry_a_bad_request(self):
        a = fake(errors.BadRequestError("bad"), "never")
        client = FallbackClient([("a", a)], attempts_per_model=3, sleep=no_sleep)
        with pytest.raises(errors.BadRequestError):
            client.chat(MSGS)
        assert a.call_count == 1

class TestBreakers:
    def test_open_breaker_skips_the_model_without_calling_it(self):
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure()
        a, b = fake("never"), fake("from b")
        client = FallbackClient([("a", a), ("b", b)], breakers={"a": breaker})
        assert client.chat(MSGS).text == "from b"
        assert a.call_count == 0
        assert client.last_attempts[0].skipped is True

    def test_retryable_failure_is_recorded_on_the_breaker(self):
        breaker = CircuitBreaker(failure_threshold=2)
        a = fake(errors.ServerError("1"), errors.ServerError("2"))
        client = FallbackClient([("a", a), ("b", fake())], breakers={"a": breaker})
        client.chat(MSGS)
        client.chat(MSGS)
        assert breaker.state is BreakerState.OPEN

    def test_success_is_recorded_on_the_breaker(self):
        breaker = CircuitBreaker(failure_threshold=2)
        a = fake(errors.ServerError("1"), "ok", errors.ServerError("2"))
        client = FallbackClient([("a", a), ("b", fake())], breakers={"a": breaker})
        for _ in range(3):
            client.chat(MSGS)
        # fail, succeed (resets), fail -> still one consecutive failure
        assert breaker.state is BreakerState.CLOSED

    def test_bad_request_does_not_count_against_the_breaker(self):
        breaker = CircuitBreaker(failure_threshold=1)
        a = fake(errors.BadRequestError("my bug"))
        client = FallbackClient([("a", a)], breakers={"a": breaker})
        with pytest.raises(errors.BadRequestError):
            client.chat(MSGS)
        assert breaker.state is BreakerState.CLOSED, "the provider is fine; you are not"

    def test_every_breaker_open_raises_all_models_failed(self):
        breakers = {n: CircuitBreaker(failure_threshold=1) for n in ("a", "b")}
        for b in breakers.values():
            b.record_failure()
        client = FallbackClient([("a", fake()), ("b", fake())], breakers=breakers)
        with pytest.raises(AllModelsFailed) as exc:
            client.chat(MSGS)
        assert all(a.skipped for a in exc.value.attempts)


class TestConstruction:
    def test_empty_chain_is_rejected(self):
        with pytest.raises(ValueError):
            FallbackClient([])

    def test_duplicate_names_are_rejected(self):
        with pytest.raises(ValueError):
            FallbackClient([("a", fake()), ("a", fake())])
