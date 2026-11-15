"""Tests for Chapter 7, Exercise 1 — the plan structure."""

import pytest

from chapters.ch07_planning.exercises.exercise_1_plan import Plan, PlanStep, StepStatus


def plan(*specs):
    """specs: (id, depends_on) tuples."""
    return Plan(goal="g", steps=[
        PlanStep(id=i, description=f"step {i}", depends_on=list(deps))
        for i, deps in specs
    ])


class TestStatus:
    def test_five_states(self):
        assert {s.value for s in StepStatus} == {
            "pending", "running", "done", "failed", "skipped"
        }


class TestStep:
    def test_defaults(self):
        s = PlanStep(id=1, description="x")
        assert s.status is StepStatus.PENDING
        assert s.depends_on == []
        assert s.result == ""

    @pytest.mark.parametrize("status,expected", [
        (StepStatus.PENDING, False), (StepStatus.RUNNING, False),
        (StepStatus.DONE, True), (StepStatus.FAILED, True), (StepStatus.SKIPPED, True),
    ])
    def test_finished(self, status, expected):
        s = PlanStep(id=1, description="x", status=status)
        assert s.finished is expected

    def test_defaults_are_not_shared(self):
        a, b = PlanStep(id=1, description="a"), PlanStep(id=2, description="b")
        a.depends_on.append(9)
        assert b.depends_on == []


class TestPlan:
    def test_len_and_get(self):
        p = plan((1, []), (2, []))
        assert len(p) == 2
        assert p.get(2).id == 2
        assert p.get(9) is None

    def test_complete_when_all_finished(self):
        p = plan((1, []), (2, []))
        assert not p.complete
        p.get(1).status = StepStatus.DONE
        assert not p.complete
        p.get(2).status = StepStatus.FAILED
        assert p.complete, "FAILED is a terminal state; complete != succeeded"

    def test_failed(self):
        p = plan((1, []))
        assert not p.failed
        p.get(1).status = StepStatus.FAILED
        assert p.failed

    def test_empty_plan_is_complete(self):
        assert Plan(goal="g").complete


class TestReadySteps:
    def test_independent_steps_are_all_ready(self):
        p = plan((1, []), (2, []), (3, []))
        assert [s.id for s in p.ready_steps()] == [1, 2, 3], (
            "returning one step at a time throws away the parallelism"
        )

    def test_dependents_wait(self):
        p = plan((1, []), (2, [1]))
        assert [s.id for s in p.ready_steps()] == [1]

    def test_dependents_become_ready(self):
        p = plan((1, []), (2, [1]))
        p.get(1).status = StepStatus.DONE
        assert [s.id for s in p.ready_steps()] == [2]

    def test_all_dependencies_must_be_done(self):
        p = plan((1, []), (2, []), (3, [1, 2]))
        p.get(1).status = StepStatus.DONE
        assert [s.id for s in p.ready_steps()] == [2]

    def test_failed_dependency_blocks(self):
        p = plan((1, []), (2, [1]))
        p.get(1).status = StepStatus.FAILED
        assert p.ready_steps() == []

    def test_running_steps_are_not_ready_again(self):
        p = plan((1, []))
        p.get(1).status = StepStatus.RUNNING
        assert p.ready_steps() == []

    def test_done_steps_are_not_ready(self):
        p = plan((1, []))
        p.get(1).status = StepStatus.DONE
        assert p.ready_steps() == []


class TestSkipBlocked:
    def test_skips_a_dependent_of_a_failure(self):
        p = plan((1, []), (2, [1]))
        p.get(1).status = StepStatus.FAILED
        skipped = p.skip_blocked()
        assert [s.id for s in skipped] == [2]
        assert p.get(2).status is StepStatus.SKIPPED

    def test_cascades_transitively(self):
        p = plan((1, []), (2, [1]), (3, [2]), (4, [3]))
        p.get(1).status = StepStatus.FAILED
        p.skip_blocked()
        assert all(p.get(i).status is StepStatus.SKIPPED for i in (2, 3, 4))

    def test_leaves_independent_steps_alone(self):
        p = plan((1, []), (2, [1]), (3, []))
        p.get(1).status = StepStatus.FAILED
        p.skip_blocked()
        assert p.get(3).status is StepStatus.PENDING

    def test_no_failures_skips_nothing(self):
        p = plan((1, []), (2, [1]))
        assert p.skip_blocked() == []

    def test_records_a_reason(self):
        p = plan((1, []), (2, [1]))
        p.get(1).status = StepStatus.FAILED
        p.skip_blocked()
        assert p.get(2).result

    def test_makes_a_blocked_plan_complete(self):
        # without this the executor spins forever finding nothing ready
        p = plan((1, []), (2, [1]))
        p.get(1).status = StepStatus.FAILED
        p.skip_blocked()
        assert p.complete

    def test_is_idempotent(self):
        p = plan((1, []), (2, [1]))
        p.get(1).status = StepStatus.FAILED
        p.skip_blocked()
        assert p.skip_blocked() == []


class TestRender:
    def test_includes_the_goal(self):
        assert "g" in plan((1, [])).render()

    def test_shows_each_step(self):
        out = plan((1, []), (2, [1])).render()
        assert "step 1" in out and "step 2" in out

    def test_shows_dependencies(self):
        assert "1" in plan((1, []), (2, [1])).render()

    def test_status_markers_differ(self):
        p = plan((1, []), (2, []))
        p.get(1).status = StepStatus.DONE
        p.get(2).status = StepStatus.FAILED
        out = p.render()
        assert "[x]" in out and "[!]" in out

    def test_includes_results(self):
        p = plan((1, []))
        p.get(1).status = StepStatus.DONE
        p.get(1).result = "found timeout=30"
        assert "found timeout=30" in p.render()

    def test_truncates_long_results(self):
        p = plan((1, []))
        p.get(1).result = "x" * 5000
        assert len(p.render()) < 1000, "plan.render() goes into a context window"
