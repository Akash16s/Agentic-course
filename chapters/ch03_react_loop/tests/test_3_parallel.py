"""Tests for Chapter 3, Exercise 3 — parallel tool execution."""

import threading
import time

import pytest

from agentlib.errors import StopSignal
from agentlib.tools import ToolCall, ToolRegistry, tool
from chapters.ch03_react_loop.exercises.exercise_3_parallel import run_tools


@tool
def slow(n: int) -> int:
    """Sleep 100ms then echo n."""
    time.sleep(0.1)
    return n


@tool
def echo(text: str) -> str:
    """Echo text."""
    return text


@tool
def stopper(answer: str) -> str:
    """Finish the run."""
    raise StopSignal(answer)


@tool
def boom() -> str:
    """Always fails."""
    raise RuntimeError("kaboom")


REG = ToolRegistry([slow, echo, stopper, boom])


def calls(*specs):
    return [
        ToolCall(id=f"c{i}", name=name, arguments=args)
        for i, (name, args) in enumerate(specs)
    ]


class TestOrdering:
    def test_empty(self):
        assert run_tools(REG, []) == []

    def test_single_call(self):
        msgs = run_tools(REG, calls(("echo", {"text": "hi"})))
        assert len(msgs) == 1
        assert msgs[0]["content"] == "hi"

    def test_order_is_preserved_in_parallel(self):
        # varying sleeps so completion order differs from input order
        @tool
        def variable(ms: int) -> int:
            """Sleep then echo."""
            time.sleep(ms / 1000)
            return ms

        reg = ToolRegistry([variable])
        cs = calls(*[("variable", {"ms": ms}) for ms in (120, 10, 60, 5)])
        msgs = run_tools(reg, cs, parallel=True)
        assert [m["content"] for m in msgs] == ["120", "10", "60", "5"]
        assert [m["tool_call_id"] for m in msgs] == ["c0", "c1", "c2", "c3"]

    def test_serial_matches_parallel_output(self):
        cs = calls(("echo", {"text": "a"}), ("echo", {"text": "b"}))
        assert run_tools(REG, cs, parallel=False) == run_tools(REG, cs, parallel=True)


class TestConcurrency:
    def test_parallel_is_actually_faster(self):
        cs = calls(*[("slow", {"n": i}) for i in range(4)])

        t0 = time.monotonic()
        run_tools(REG, cs, parallel=False)
        serial = time.monotonic() - t0

        t0 = time.monotonic()
        run_tools(REG, cs, parallel=True)
        concurrent = time.monotonic() - t0

        assert serial > 0.35, "4 x 100ms should take ~400ms serially"
        assert concurrent < serial / 2, "parallel should be several times faster"

    def test_worker_cap_is_respected(self):
        live = 0
        peak = 0
        lock = threading.Lock()

        @tool
        def counted(i: int) -> int:
            """Track concurrency."""
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            time.sleep(0.05)
            with lock:
                live -= 1
            return i

        reg = ToolRegistry([counted])
        cs = calls(*[("counted", {"i": i}) for i in range(20)])
        run_tools(reg, cs, parallel=True)
        assert peak <= 8, f"opened {peak} threads; cap is MAX_WORKERS=8"

    def test_single_call_does_not_need_parallelism(self):
        # a thread pool for one call is pure overhead; just checking it still works
        assert run_tools(REG, calls(("echo", {"text": "x"})), parallel=True)[0]["content"] == "x"


class TestFailures:
    def test_tool_error_becomes_a_message(self):
        msgs = run_tools(REG, calls(("boom", {})))
        assert len(msgs) == 1
        assert "RuntimeError" in msgs[0]["content"]

    def test_one_failure_does_not_lose_the_others(self):
        cs = calls(("echo", {"text": "ok"}), ("boom", {}), ("echo", {"text": "also ok"}))
        msgs = run_tools(REG, cs, parallel=True)
        assert len(msgs) == 3, "every call needs a result, including the failed one"
        assert msgs[0]["content"] == "ok"
        assert msgs[2]["content"] == "also ok"

    def test_unknown_tool_still_yields_a_message(self):
        msgs = run_tools(REG, calls(("nope", {})))
        assert "unknown tool" in msgs[0]["content"]


class TestStopSignal:
    def test_propagates_serially(self):
        with pytest.raises(StopSignal):
            run_tools(REG, calls(("stopper", {"answer": "42"})), parallel=False)

    def test_propagates_from_a_worker_thread(self):
        cs = calls(("echo", {"text": "a"}), ("stopper", {"answer": "42"}))
        with pytest.raises(StopSignal) as exc:
            run_tools(REG, cs, parallel=True)
        assert exc.value.output == "42"

    def test_is_not_converted_into_an_error_result(self):
        # the one exception to "tool failures are data": this is control flow
        with pytest.raises(StopSignal):
            run_tools(REG, calls(("stopper", {"answer": "x"})))
