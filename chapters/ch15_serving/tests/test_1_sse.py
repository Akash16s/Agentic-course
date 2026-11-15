"""Tests for Chapter 15, Exercise 1 — SSE framing."""

import json

import pytest

from chapters.ch15_serving.exercises.exercise_1_sse import sse, sse_done, sse_error


class TestFraming:
    def test_simple(self):
        assert sse("hello") == "data: hello\n\n"

    def test_ends_with_a_blank_line(self):
        # the blank line is what flushes the frame; one \n and the client hangs
        for frame in [sse("x"), sse({"a": 1}), sse("x", event="e")]:
            assert frame.endswith("\n\n")

    def test_event_field(self):
        assert sse("x", event="delta").startswith("event: delta\n")

    def test_id_field(self):
        assert "id: 7\n" in sse("x", id="7")

    def test_field_order(self):
        frame = sse("x", event="delta", id="7")
        assert frame.index("event:") < frame.index("id:") < frame.index("data:")

    def test_no_optional_fields(self):
        frame = sse("x")
        assert "event:" not in frame
        assert "id:" not in frame


class TestPayload:
    def test_string_is_used_as_is(self):
        assert "data: plain text\n" in sse("plain text")

    def test_dict_is_json_encoded(self):
        frame = sse({"text": "hi", "n": 1})
        payload = frame.split("data: ")[1].split("\n")[0]
        assert json.loads(payload) == {"text": "hi", "n": 1}

    def test_list_is_json_encoded(self):
        assert "data: [1, 2]" in sse([1, 2])

    def test_multiline_gets_a_prefix_per_line(self):
        # without this, everything after the first newline is silently dropped
        assert sse("two\nlines") == "data: two\ndata: lines\n\n"

    def test_multiline_json(self):
        frame = sse(json.dumps({"a": 1}, indent=2))
        for line in frame.strip().split("\n"):
            assert line.startswith("data: ")

    def test_empty_string(self):
        assert sse("") == "data: \n\n"

    def test_trailing_newline_in_content(self):
        frame = sse("text\n")
        assert frame.count("data: ") == 2


class TestHelpers:
    def test_done_sentinel(self):
        # browsers auto-reconnect on a bare close and re-run the whole agent
        frame = sse_done()
        assert "[DONE]" in frame
        assert "event: done" in frame
        assert frame.endswith("\n\n")

    def test_error_frame(self):
        frame = sse_error("provider timeout")
        assert "event: error" in frame
        assert "provider timeout" in frame
        assert frame.endswith("\n\n")

    def test_error_payload_is_json(self):
        frame = sse_error("boom")
        payload = frame.split("data: ")[1].split("\n")[0]
        assert json.loads(payload) == {"error": "boom"}


class TestStreamShape:
    def test_a_realistic_stream_parses(self):
        stream = "".join([
            sse({"text": "Hello"}, event="delta"),
            sse({"text": " world"}, event="delta"),
            sse({"cost": 0.001}, event="usage"),
            sse_done(),
        ])
        frames = [f for f in stream.split("\n\n") if f.strip()]
        assert len(frames) == 4
        assert frames[-1].startswith("event: done")

    def test_error_can_appear_mid_stream(self):
        # you cannot change the status code after the first byte
        stream = sse({"text": "Hel"}, event="delta") + sse_error("provider died")
        assert "event: error" in stream
