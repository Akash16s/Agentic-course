"""Tests for Chapter 15, Exercise 2 — durable run state."""

import json
import time

import pytest

from chapters.ch15_serving.exercises.exercise_2_runstore import (
    Run,
    RunStatus,
    RunStore,
)


@pytest.fixture
def store(tmp_path):
    return RunStore(str(tmp_path / "runs.db"))


class TestStatus:
    def test_five_states(self):
        assert {s.value for s in RunStatus} == {
            "queued", "running", "succeeded", "failed", "cancelled"
        }


class TestRun:
    def test_defaults(self):
        run = Run(id="a", task="t")
        assert run.status is RunStatus.QUEUED
        assert run.session_id == "default"
        assert run.attempts == 0
        assert run.cost == 0.0

    @pytest.mark.parametrize("status,expected", [
        (RunStatus.QUEUED, False), (RunStatus.RUNNING, False),
        (RunStatus.SUCCEEDED, True), (RunStatus.FAILED, True),
        (RunStatus.CANCELLED, True),
    ])
    def test_terminal(self, status, expected):
        assert Run(id="a", task="t", status=status).terminal is expected

    def test_to_dict_is_json_serialisable(self):
        json.dumps(Run(id="a", task="t").to_dict())

    def test_to_dict_uses_the_status_string(self):
        assert Run(id="a", task="t").to_dict()["status"] == "queued"


class TestStore:
    def test_create(self, store):
        run = store.create("do a thing")
        assert run.id
        assert run.status is RunStatus.QUEUED
        assert store.get(run.id) is not None

    def test_explicit_id(self, store):
        assert store.create("t", run_id="my-id").id == "my-id"

    def test_get_missing(self, store):
        assert store.get("nope") is None

    def test_round_trip(self, store):
        run = store.create("task", session_id="s1")
        loaded = store.get(run.id)
        assert loaded.task == "task"
        assert loaded.session_id == "s1"

    def test_save_updates(self, store):
        run = store.create("task")
        run.status = RunStatus.SUCCEEDED
        run.output = "the answer"
        run.cost = 0.42
        store.save(run)
        loaded = store.get(run.id)
        assert loaded.status is RunStatus.SUCCEEDED
        assert loaded.output == "the answer"
        assert loaded.cost == 0.42

    def test_save_refreshes_updated_at(self, store):
        # the heartbeat reclaim_stale depends on
        run = store.create("task")
        first = store.get(run.id).updated_at
        time.sleep(0.01)
        store.save(run)
        assert store.get(run.id).updated_at > first

    def test_created_at_is_preserved(self, store):
        run = store.create("task")
        original = run.created_at
        store.save(run)
        assert store.get(run.id).created_at == original


class TestDurability:
    def test_survives_a_new_store_object(self, tmp_path):
        path = str(tmp_path / "runs.db")
        run = RunStore(path).create("task")
        assert RunStore(path).get(run.id) is not None

    def test_list_newest_first(self, store):
        first = store.create("one")
        time.sleep(0.01)
        second = store.create("two")
        assert [r.id for r in store.list()][:2] == [second.id, first.id]

    def test_list_by_session(self, store):
        store.create("a", session_id="s1")
        store.create("b", session_id="s2")
        assert len(store.list(session_id="s1")) == 1

    def test_list_limit(self, store):
        for i in range(10):
            store.create(f"task {i}")
        assert len(store.list(limit=3)) == 3


class TestReclaim:
    def stale(self, store, *, age=1000, attempts=0):
        run = store.create("stranded")
        run.status = RunStatus.RUNNING
        run.attempts = attempts
        store.save(run)
        conn = store._connect()
        with conn:
            conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?",
                         (time.time() - age, run.id))
        return run

    def test_requeues_an_abandoned_run(self, store):
        # a worker OOM-killed mid-run leaves this row saying RUNNING forever
        run = self.stale(store)
        reclaimed = store.reclaim_stale(older_than_s=300)
        assert [r.id for r in reclaimed] == [run.id]
        assert store.get(run.id).status is RunStatus.QUEUED

    def test_leaves_fresh_runs_alone(self, store):
        run = store.create("busy")
        run.status = RunStatus.RUNNING
        store.save(run)
        assert store.reclaim_stale(older_than_s=300) == []
        assert store.get(run.id).status is RunStatus.RUNNING

    def test_leaves_terminal_runs_alone(self, store):
        run = store.create("finished")
        run.status = RunStatus.SUCCEEDED
        store.save(run)
        conn = store._connect()
        with conn:
            conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?",
                         (time.time() - 1000, run.id))
        assert store.reclaim_stale(older_than_s=300) == []

    def test_poison_pill_is_failed_not_requeued(self, store):
        # a run that reliably kills its worker would otherwise take out the fleet
        run = self.stale(store, attempts=3)
        store.reclaim_stale(older_than_s=300, max_attempts=3)
        loaded = store.get(run.id)
        assert loaded.status is RunStatus.FAILED
        assert "abandoned" in loaded.error

    def test_under_the_attempt_limit_is_requeued(self, store):
        run = self.stale(store, attempts=1)
        store.reclaim_stale(older_than_s=300, max_attempts=3)
        assert store.get(run.id).status is RunStatus.QUEUED

    def test_several_at_once(self, store):
        for _ in range(3):
            self.stale(store)
        assert len(store.reclaim_stale(older_than_s=300)) == 3
