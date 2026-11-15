"""Tests for Exercise 5 — streaming."""

import pytest

from agentlib.llm import LLMResponse, Usage
from agentlib.testing import FakeLLMClient, _FakeChunk
from chapters.ch01_agent_loop.exercises.exercise_5_stream import stream_chat

MSGS = [{"role": "user", "content": "hi"}]


class StubStreamClient:
    """Yields an exact, hand-written chunk sequence — including the awkward ones."""

    def __init__(self, chunks):
        self._chunks = chunks

    def stream_raw(self, messages, **kwargs):
        yield from self._chunks


class TestStreamChat:
    def test_accumulates_text(self):
        client = FakeLLMClient(["the quick brown fox"])
        r = stream_chat(client, MSGS)
        assert r.text == "the quick brown fox"

    def test_calls_on_delta_for_each_piece(self):
        pieces = []
        client = FakeLLMClient(["one two three"])
        stream_chat(client, MSGS, on_delta=pieces.append)
        assert len(pieces) == 3
        assert "".join(pieces) == "one two three"

    def test_works_without_on_delta(self):
        client = FakeLLMClient(["hello"])
        assert stream_chat(client, MSGS).text == "hello"

    def test_returns_an_llm_response(self):
        client = FakeLLMClient(["hi"])
        assert isinstance(stream_chat(client, MSGS), LLMResponse)

    def test_captures_usage_from_the_final_chunk(self):
        client = FakeLLMClient(
            [LLMResponse(text="a b", usage=Usage(42, 7), model="fake/model")]
        )
        r = stream_chat(client, MSGS)
        assert r.usage.prompt_tokens == 42
        assert r.usage.completion_tokens == 7

    def test_captures_finish_reason(self):
        client = FakeLLMClient(
            [LLMResponse(text="cut off here", finish_reason="length")]
        )
        r = stream_chat(client, MSGS)
        assert r.finish_reason == "length"
        assert r.truncated

    def test_defaults_finish_reason_to_stop(self):
        r = stream_chat(StubStreamClient([_FakeChunk(delta_content="hi")]), MSGS)
        assert r.finish_reason == "stop"

    def test_survives_chunks_with_no_choices(self):
        # The usage-only final chunk has choices == []. Indexing [0] blindly crashes.
        chunks = [
            _FakeChunk(delta_content="hello"),
            _FakeChunk(usage=Usage(5, 2)),
        ]
        r = stream_chat(StubStreamClient(chunks), MSGS)
        assert r.text == "hello"
        assert r.usage.prompt_tokens == 5

    def test_survives_none_content_deltas(self):
        # Role-announcement and tool-call chunks carry content=None.
        chunks = [
            _FakeChunk(delta_content=None, finish_reason=None),
            _FakeChunk(delta_content="real"),
            _FakeChunk(delta_content=None, finish_reason="stop"),
        ]
        pieces = []
        r = stream_chat(StubStreamClient(chunks), MSGS, on_delta=pieces.append)
        assert r.text == "real"
        assert pieces == ["real"], "None must not be passed to on_delta"

    def test_zero_usage_when_none_arrives(self):
        r = stream_chat(StubStreamClient([_FakeChunk(delta_content="x")]), MSGS)
        assert r.usage.total_tokens == 0

    def test_passes_kwargs_through(self):
        client = FakeLLMClient(["ok"])
        stream_chat(client, MSGS, temperature=0.3, max_tokens=99)
        _, kwargs = client.calls[0]
        assert kwargs["temperature"] == 0.3
        assert kwargs["max_tokens"] == 99
        assert "on_delta" not in kwargs, "on_delta is ours, not the API's"

    def test_empty_stream_gives_empty_text(self):
        r = stream_chat(StubStreamClient([]), MSGS)
        assert r.text == ""
