"""Tests for Exercise 1 — token estimation.  Offline, free, instant."""

import pytest

from chapters.ch01_agent_loop.exercises.exercise_1_tokens import (
    PER_MESSAGE_OVERHEAD,
    REPLY_PRIMING,
    estimate_messages_tokens,
    estimate_tokens,
    fits_in_budget,
)


class TestEstimateTokens:
    def test_empty_string_is_zero(self):
        assert estimate_tokens("") == 0

    def test_exactly_one_token(self):
        assert estimate_tokens("abcd") == 1

    def test_rounds_up_not_down(self):
        # 5 chars / 4 = 1.25 -> must be 2. Under-estimating context is the dangerous
        # direction: you find out at request time, after you have already paid.
        assert estimate_tokens("abcde") == 2

    def test_single_char(self):
        assert estimate_tokens("a") == 1

    def test_longer_text(self):
        assert estimate_tokens("x" * 400) == 100

    def test_is_within_20_percent_of_reality(self):
        # A real sentence. Real tokenizers give ~11-13 tokens for this.
        text = "The quick brown fox jumps over the lazy dog near the river bank."
        assert 10 <= estimate_tokens(text) <= 20


class TestEstimateMessagesTokens:
    def test_empty_list_is_zero(self):
        assert estimate_messages_tokens([]) == 0

    def test_single_message(self):
        msgs = [{"role": "user", "content": "abcd"}]
        assert estimate_messages_tokens(msgs) == 1 + PER_MESSAGE_OVERHEAD + REPLY_PRIMING

    def test_priming_counted_once_not_per_message(self):
        one = estimate_messages_tokens([{"role": "user", "content": "abcd"}])
        two = estimate_messages_tokens(
            [{"role": "user", "content": "abcd"}, {"role": "assistant", "content": "abcd"}]
        )
        assert two - one == 1 + PER_MESSAGE_OVERHEAD

    def test_handles_none_content(self):
        # Happens with tool-call messages in Chapter 2. Must not crash.
        msgs = [{"role": "assistant", "content": None}]
        assert estimate_messages_tokens(msgs) == PER_MESSAGE_OVERHEAD + REPLY_PRIMING

    def test_handles_missing_content_key(self):
        assert estimate_messages_tokens([{"role": "user"}]) == (
            PER_MESSAGE_OVERHEAD + REPLY_PRIMING
        )

    def test_grows_with_history(self):
        short = [{"role": "user", "content": "hi"}]
        long = [{"role": "user", "content": "hi"}] * 10
        assert estimate_messages_tokens(long) > estimate_messages_tokens(short)


class TestFitsInBudget:
    def test_small_message_fits(self):
        assert fits_in_budget([{"role": "user", "content": "hi"}], 100, reserve_for_output=10)

    def test_big_message_does_not_fit(self):
        assert not fits_in_budget([{"role": "user", "content": "x" * 4000}], 100)

    def test_reserve_is_respected(self):
        msgs = [{"role": "user", "content": "x" * 200}]  # ~50 tokens + 7 overhead
        assert fits_in_budget(msgs, 100, reserve_for_output=10)
        # same prompt, same window, but now we want room for 500 output tokens
        assert not fits_in_budget(msgs, 100, reserve_for_output=500)

    def test_boundary_is_inclusive(self):
        msgs = [{"role": "user", "content": "abcd"}]  # 1 + 4 + 3 = 8
        assert fits_in_budget(msgs, 10, reserve_for_output=2)   # 8 + 2 == 10 -> fits
        assert not fits_in_budget(msgs, 10, reserve_for_output=3)
