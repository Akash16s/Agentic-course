"""Tests for Chapter 16, Exercise 1 — JSON-RPC."""

import json

import pytest

from chapters.ch16_mcp.exercises.exercise_1_protocol import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    Request,
    Response,
    encode,
    error_response,
    parse_message,
    read_messages,
)


class TestRequest:
    def test_to_dict(self):
        assert Request("ping", id=1).to_dict() == {
            "jsonrpc": "2.0", "method": "ping", "id": 1
        }

    def test_params_included_when_present(self):
        d = Request("tools/call", {"name": "add"}, id=1).to_dict()
        assert d["params"] == {"name": "add"}

    def test_empty_params_omitted(self):
        assert "params" not in Request("ping", {}, id=1).to_dict()

    def test_notification_omits_the_id(self):
        # `"id": null` is a request with a null id, which is a DIFFERENT thing
        d = Request("notifications/initialized").to_dict()
        assert "id" not in d

    def test_is_notification(self):
        assert Request("x").is_notification
        assert not Request("x", id=1).is_notification
        assert not Request("x", id="abc").is_notification

    def test_id_zero_is_still_a_request(self):
        assert not Request("x", id=0).is_notification


class TestResponse:
    def test_result(self):
        assert Response(id=1, result={"a": 1}).to_dict() == {
            "jsonrpc": "2.0", "id": 1, "result": {"a": 1}
        }

    def test_error(self):
        d = Response(id=1, error={"code": -1, "message": "x"}).to_dict()
        assert d["error"]["code"] == -1
        assert "result" not in d, "never both keys"

    def test_ok(self):
        assert Response(id=1, result="x").ok
        assert not Response(id=1, error={"code": -1, "message": "x"}).ok

    def test_null_result_is_still_a_result(self):
        assert Response(id=1, result=None).to_dict()["result"] is None


class TestErrorResponse:
    def test_shape(self):
        r = error_response(1, METHOD_NOT_FOUND, "unknown method: foo")
        assert r.error == {"code": METHOD_NOT_FOUND, "message": "unknown method: foo"}

    def test_optional_data(self):
        r = error_response(1, INVALID_PARAMS, "bad", data={"field": "name"})
        assert r.error["data"] == {"field": "name"}

    def test_data_omitted_when_none(self):
        assert "data" not in error_response(1, -1, "x").error


class TestParseMessage:
    def test_request(self):
        message = parse_message('{"jsonrpc":"2.0","method":"ping","id":1}')
        assert isinstance(message, Request)
        assert message.method == "ping" and message.id == 1

    def test_notification(self):
        message = parse_message('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        assert isinstance(message, Request) and message.is_notification

    def test_response_with_result(self):
        message = parse_message('{"jsonrpc":"2.0","id":1,"result":{"a":1}}')
        assert isinstance(message, Response) and message.result == {"a": 1}

    def test_response_with_error(self):
        message = parse_message('{"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"x"}}')
        assert isinstance(message, Response) and not message.ok

    def test_params_defaults_to_a_dict(self):
        assert parse_message('{"method":"x","id":1}').params == {}

    def test_non_dict_params_become_a_dict(self):
        assert parse_message('{"method":"x","params":[1,2],"id":1}').params == {}

    def test_invalid_json(self):
        assert parse_message("{not json") is None

    def test_not_an_object(self):
        assert parse_message("[1,2]") is None
        assert parse_message('"a string"') is None

    def test_neither_request_nor_response(self):
        assert parse_message('{"jsonrpc":"2.0"}') is None

    def test_never_raises(self):
        for raw in ["", "{", "null", "[]", "123", '{"jsonrpc":"2.0"}']:
            parse_message(raw)


class TestEncoding:
    def test_one_line_terminated(self):
        line = encode(Request("ping", id=1))
        assert line.endswith("\n")
        assert line.count("\n") == 1

    def test_round_trip(self):
        original = Request("tools/call", {"name": "add"}, id=7)
        parsed = parse_message(encode(original).strip())
        assert parsed.method == original.method
        assert parsed.params == original.params
        assert parsed.id == original.id

    def test_newlines_in_content_are_escaped(self):
        # the property that makes newline-delimited framing work at all
        line = encode(Response(id=1, result={"text": "two\nlines"}))
        assert line.count("\n") == 1

    def test_non_ascii_is_readable(self):
        assert "café" in encode(Response(id=1, result={"t": "café"}))


class TestReadMessages:
    def test_reads_a_stream(self):
        stream = iter([
            encode(Request("ping", id=1)),
            encode(Response(id=1, result={})),
        ])
        assert len(list(read_messages(stream))) == 2

    def test_skips_blank_lines(self):
        stream = iter(["\n", "  \n", encode(Request("ping", id=1)), "\n"])
        assert len(list(read_messages(stream))) == 1

    def test_skips_garbage_rather_than_dying(self):
        # one stray log write must not kill the server
        stream = iter([
            "starting up...\n",
            encode(Request("ping", id=1)),
            "{broken\n",
            encode(Request("ping", id=2)),
        ])
        assert len(list(read_messages(stream))) == 2

    def test_empty_stream(self):
        assert list(read_messages(iter([]))) == []
