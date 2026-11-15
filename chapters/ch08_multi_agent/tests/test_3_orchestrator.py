"""Tests for Chapter 8, Exercise 3 — fan-out."""

import threading
import time

import pytest

from chapters.ch08_multi_agent.exercises.exercise_3_orchestrator import (
    Orchestrator,
    WorkerResult,
)


def slow(delay=0.1):
    def worker(task):
        time.sleep(delay)
        return f"did {task}"
    return worker


def boom(task):
    raise RuntimeError("worker died")


WORKERS = {"a": slow(), "b": slow(), "c": slow(), "d": slow(), "bad": boom}


class TestWorkerResult:
    def test_ok(self):
        assert WorkerResult(name="a", task="t").ok
        assert not WorkerResult(name="a", task="t", error="boom").ok


class TestRunOne:
    def test_success(self):
        r = Orchestrator(WORKERS).run_one("a", "thing")
        assert r.ok
        assert r.output == "did thing"
        assert r.name == "a" and r.task == "thing"

    def test_records_duration(self):
        assert Orchestrator(WORKERS).run_one("a", "t").duration_s > 0

    def test_unknown_worker(self):
        r = Orchestrator(WORKERS).run_one("nope", "t")
        assert not r.ok
        assert "no worker" in r.error

    def test_raising_worker_is_captured(self):
        r = Orchestrator(WORKERS).run_one("bad", "t")
        assert not r.ok
        assert "RuntimeError" in r.error
        assert "worker died" in r.error

    def test_never_raises(self):
        o = Orchestrator(WORKERS)
        o.run_one("bad", "t")
        o.run_one("missing", "t")

    def test_non_string_output_is_stringified(self):
        o = Orchestrator({"n": lambda t: 42})
        assert o.run_one("n", "t").output == "42"


class TestFanOut:
    def test_empty(self):
        assert Orchestrator(WORKERS).fan_out([]) == []

    def test_all_results_returned(self):
        results = Orchestrator(WORKERS).fan_out([("a", "1"), ("b", "2"), ("c", "3")])
        assert len(results) == 3

    def test_order_is_preserved(self):
        workers = {f"w{i}": slow(0.05 * (5 - i)) for i in range(5)}
        o = Orchestrator(workers, max_parallel=5)
        results = o.fan_out([(f"w{i}", f"t{i}") for i in range(5)])
        assert [r.name for r in results] == [f"w{i}" for i in range(5)]

    def test_runs_in_parallel(self):
        o = Orchestrator(WORKERS, max_parallel=4)
        started = time.monotonic()
        o.fan_out([("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")])
        elapsed = time.monotonic() - started
        assert elapsed < 0.25, f"4 x 100ms took {elapsed:.2f}s; not parallel"

    def test_max_parallel_one_is_serial(self):
        o = Orchestrator(WORKERS, max_parallel=1)
        started = time.monotonic()
        o.fan_out([("a", "1"), ("b", "2")])
        assert time.monotonic() - started >= 0.18

    def test_concurrency_is_capped(self):
        live = peak = 0
        lock = threading.Lock()

        def counted(task):
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            time.sleep(0.05)
            with lock:
                live -= 1
            return "ok"

        o = Orchestrator({f"w{i}": counted for i in range(20)}, max_parallel=3)
        o.fan_out([(f"w{i}", "t") for i in range(20)])
        assert peak <= 3, f"opened {peak} workers; cap was 3"

    def test_one_failure_does_not_lose_the_others(self):
        results = Orchestrator(WORKERS).fan_out(
            [("a", "1"), ("bad", "2"), ("c", "3")]
        )
        assert len(results) == 3
        assert [r.ok for r in results] == [True, False, True]

    def test_fan_out_never_raises(self):
        Orchestrator(WORKERS).fan_out([("bad", "1"), ("missing", "2")])

    def test_on_result_callback(self):
        seen = []
        Orchestrator(WORKERS, on_result=seen.append).fan_out([("a", "1"), ("b", "2")])
        assert len(seen) == 2

    def test_single_assignment(self):
        results = Orchestrator(WORKERS).fan_out([("a", "only")])
        assert len(results) == 1 and results[0].ok
