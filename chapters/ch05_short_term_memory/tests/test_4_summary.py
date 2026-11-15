"""Tests for Chapter 5, Exercise 4 — SummaryBuffer."""

import pytest

from chapters.ch05_short_term_memory.exercises.exercise_4_summary import SummaryBuffer


class CountingSummariser:
    """Records every call, so we can prove the cache works."""

    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, transcript: str) -> str:
        self.calls.append(transcript)
        return f"SUMMARY-{len(self.calls)}"

    @property
    def count(self) -> int:
        return len(self.calls)


def msgs(n, size=200):
    return [{"role": "user", "content": f"turn {i} " + "x" * size} for i in range(n)]


class TestNoOp:
    def test_short_history_is_passed_through(self):
        s = CountingSummariser()
        buf = SummaryBuffer(s, max_tokens=10_000, keep_recent=4)
        m = msgs(3)
        assert buf.build(m) == m
        assert s.count == 0, "no API call when there is nothing to compact"

    def test_no_summary_yet(self):
        buf = SummaryBuffer(CountingSummariser(), max_tokens=10_000)
        buf.build(msgs(2))
        assert buf.summary is None

    def test_under_threshold_does_nothing(self):
        s = CountingSummariser()
        # 10 short messages, generous budget -> under 70%
        buf = SummaryBuffer(s, max_tokens=10_000, keep_recent=2)
        buf.build(msgs(10, size=10))
        assert s.count == 0


class TestCompaction:
    def test_compacts_when_over_threshold(self):
        s = CountingSummariser()
        buf = SummaryBuffer(s, max_tokens=200, keep_recent=3)
        out = buf.build(msgs(20))
        assert s.count == 1
        assert len(out) == 4
        assert "SUMMARY-1" in out[0]["content"]

    def test_summary_is_cached(self):
        buf = SummaryBuffer(CountingSummariser(), max_tokens=200, keep_recent=3)
        buf.build(msgs(20))
        assert buf.summary is not None
        assert "SUMMARY-1" in buf.summary

    def test_summary_marker_is_a_user_message(self):
        buf = SummaryBuffer(CountingSummariser(), max_tokens=200, keep_recent=3)
        assert buf.build(msgs(20))[0]["role"] == "user"

    def test_recent_turns_are_verbatim(self):
        m = msgs(20)
        out = SummaryBuffer(CountingSummariser(), max_tokens=200, keep_recent=3).build(m)
        assert out[1:] == m[-3:]


class TestTheCache:
    def test_does_not_resummarise_the_same_messages(self):
        s = CountingSummariser()
        buf = SummaryBuffer(s, max_tokens=200, keep_recent=3)
        m = msgs(20)
        buf.build(m)
        buf.build(m)
        buf.build(m)
        assert s.count == 1, (
            "summarising every turn is a second quadratic; it can cost more "
            "than the conversation it is saving"
        )

    def test_resummarises_only_once_enough_new_material_arrives(self):
        s = CountingSummariser()
        buf = SummaryBuffer(s, max_tokens=200, keep_recent=3)
        m = msgs(20)
        buf.build(m)
        assert s.count == 1
        for i in range(20, 40):
            m.append({"role": "user", "content": f"turn {i} " + "x" * 200})
            buf.build(m)
        assert 1 < s.count <= 8, f"expected a handful of compactions, got {s.count}"

    def test_summary_survives_across_builds(self):
        buf = SummaryBuffer(CountingSummariser(), max_tokens=200, keep_recent=3)
        m = msgs(20)
        buf.build(m)
        first = buf.summary
        out = buf.build(m)
        assert buf.summary == first
        assert first in out[0]["content"]


class TestCarryForward:
    def test_previous_summary_is_fed_into_the_next_one(self):
        s = CountingSummariser()
        buf = SummaryBuffer(s, max_tokens=200, keep_recent=3)
        m = msgs(20)
        buf.build(m)
        for i in range(20, 60):
            m.append({"role": "user", "content": f"turn {i} " + "x" * 200})
            buf.build(m)

        assert s.count >= 2, "need at least two compactions to test the carry-forward"
        later = s.calls[-1]
        assert "PREVIOUS SUMMARY" in later, (
            "without carrying the old summary forward, early facts vanish for good"
        )

    def test_first_summarisation_has_no_previous(self):
        s = CountingSummariser()
        SummaryBuffer(s, max_tokens=200, keep_recent=3).build(msgs(20))
        assert "PREVIOUS SUMMARY" not in s.calls[0]

    def test_transcript_contains_the_old_turns(self):
        s = CountingSummariser()
        SummaryBuffer(s, max_tokens=200, keep_recent=3).build(msgs(20))
        assert "turn 0" in s.calls[0]
        assert "turn 19" not in s.calls[0], "recent turns are kept verbatim, not summarised"
