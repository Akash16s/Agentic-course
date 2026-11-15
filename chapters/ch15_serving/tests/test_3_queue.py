"""Tests for Chapter 15, Exercise 3 — the job queue."""

import queue
import threading
import time

import pytest

from chapters.ch15_serving.exercises.exercise_2_runstore import RunStatus, RunStore
from chapters.ch15_serving.exercises.exercise_3_queue import JobQueue


@pytest.fixture
def store(tmp_path):
    return RunStore(str(tmp_path / "runs.db"))


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class TestProcessing:
    def test_runs_a_job(self, store):
        def handler(run):
            run.output = f"did {run.task}"

        q = JobQueue(handler, store, workers=1)
        q.start()
        try:
            run = q.submit("a thing")
            assert wait_for(lambda: store.get(run.id).terminal)
            loaded = store.get(run.id)
            assert loaded.status is RunStatus.SUCCEEDED
            assert loaded.output == "did a thing"
        finally:
            q.stop()

    def test_records_attempts(self, store):
        q = JobQueue(lambda run: None, store, workers=1)
        q.start()
        try:
            run = q.submit("t")
            assert wait_for(lambda: store.get(run.id).terminal)
            assert store.get(run.id).attempts == 1
        finally:
            q.stop()

    def test_marks_running_before_the_handler(self, store):
        seen = []

        def handler(run):
            seen.append(store.get(run.id).status)

        q = JobQueue(handler, store, workers=1)
        q.start()
        try:
            run = q.submit("t")
            assert wait_for(lambda: store.get(run.id).terminal)
            assert seen == [RunStatus.RUNNING], "the heartbeat must be visible"
        finally:
            q.stop()

    def test_several_workers_run_in_parallel(self, store):
        def slow(run):
            time.sleep(0.15)

        q = JobQueue(slow, store, workers=4)
        q.start()
        try:
            started = time.monotonic()
            runs = [q.submit(f"t{i}") for i in range(4)]
            assert wait_for(lambda: all(store.get(r.id).terminal for r in runs))
            assert time.monotonic() - started < 0.45
        finally:
            q.stop()

    def test_handler_can_set_a_terminal_status_itself(self, store):
        def handler(run):
            run.status = RunStatus.CANCELLED

        q = JobQueue(handler, store, workers=1)
        q.start()
        try:
            run = q.submit("t")
            assert wait_for(lambda: store.get(run.id).terminal)
            assert store.get(run.id).status is RunStatus.CANCELLED
        finally:
            q.stop()

    def test_cancelled_runs_are_skipped(self, store):
        ran = []
        q = JobQueue(lambda run: ran.append(1), store, workers=1)
        run = store.create("t")
        run.status = RunStatus.CANCELLED
        store.save(run)
        q.start()
        try:
            q._queue.put(run.id)
            time.sleep(0.2)
            assert ran == []
        finally:
            q.stop()


class TestFailures:
    def test_a_crashing_job_fails_the_run(self, store):
        def boom(run):
            raise RuntimeError("bad task")

        q = JobQueue(boom, store, workers=1)
        q.start()
        try:
            run = q.submit("t")
            assert wait_for(lambda: store.get(run.id).terminal)
            loaded = store.get(run.id)
            assert loaded.status is RunStatus.FAILED
            assert "RuntimeError" in loaded.error
        finally:
            q.stop()

    def test_a_crashing_job_does_not_kill_the_worker(self, store):
        # otherwise throughput silently drops to zero hours later
        calls = []

        def sometimes(run):
            calls.append(run.task)
            if run.task == "bad":
                raise RuntimeError("boom")

        q = JobQueue(sometimes, store, workers=1)
        q.start()
        try:
            q.submit("bad")
            time.sleep(0.15)
            good = q.submit("good")
            assert wait_for(lambda: store.get(good.id).terminal)
            assert store.get(good.id).status is RunStatus.SUCCEEDED
        finally:
            q.stop()


class TestBackPressure:
    def test_depth(self, store):
        q = JobQueue(lambda run: time.sleep(1), store, workers=1, max_queued=10)
        # not started: nothing drains
        for i in range(3):
            q.submit(f"t{i}")
        assert q.depth == 3

    def test_rejects_when_full(self, store):
        q = JobQueue(lambda run: None, store, workers=1, max_queued=2)
        q.submit("a")
        q.submit("b")
        with pytest.raises(queue.Full):
            q.submit("c")

    def test_a_rejected_run_is_marked_failed(self, store):
        q = JobQueue(lambda run: None, store, workers=1, max_queued=1)
        q.submit("a")
        with pytest.raises(queue.Full):
            q.submit("b")
        rejected = [r for r in store.list() if r.status is RunStatus.FAILED]
        assert rejected and "full" in rejected[0].error

    def test_rejecting_fast_beats_blocking(self, store):
        # holding an HTTP worker hostage just moves the queue somewhere less visible
        q = JobQueue(lambda run: None, store, workers=1, max_queued=1)
        q.submit("a")
        started = time.monotonic()
        with pytest.raises(queue.Full):
            q.submit("b")
        assert time.monotonic() - started < 0.1


class TestLifecycle:
    def test_start_is_idempotent(self, store):
        q = JobQueue(lambda run: None, store, workers=2)
        q.start()
        q.start()
        try:
            assert len(q._threads) == 2
        finally:
            q.stop()

    def test_stop_is_prompt(self, store):
        # a flag alone makes shutdown take workers * poll_timeout
        q = JobQueue(lambda run: None, store, workers=4)
        q.start()
        started = time.monotonic()
        q.stop()
        assert time.monotonic() - started < 1.0

    def test_stop_joins_the_threads(self, store):
        q = JobQueue(lambda run: None, store, workers=2)
        q.start()
        q.stop()
        assert q._threads == []

    def test_stop_without_start(self, store):
        JobQueue(lambda run: None, store).stop()
