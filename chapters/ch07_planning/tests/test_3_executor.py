"""Tests for Chapter 7, Exercise 3 — the executor."""

import pytest

from chapters.ch07_planning.exercises.exercise_1_plan import Plan, PlanStep, StepStatus
from chapters.ch07_planning.exercises.exercise_3_executor import PlanExecutor, PlanRun


def plan(*specs):
    return Plan(goal="g", steps=[
        PlanStep(id=i, description=f"step {i}", depends_on=list(deps))
        for i, deps in specs
    ])


def ok(step, p):
    return f"result-{step.id}"


class TestHappyPath:
    def test_single_step(self):
        run = PlanExecutor(ok).execute(plan((1, [])))
        assert run.succeeded
        assert "result-1" in run.output

    def test_independent_steps_run_in_one_round(self):
        run = PlanExecutor(ok).execute(plan((1, []), (2, []), (3, [])))
        assert run.succeeded
        assert run.rounds == 1, "independent steps should not need three rounds"

    def test_dependencies_are_respected(self):
        order = []
        p = plan((1, []), (2, [1]), (3, [2]))
        PlanExecutor(lambda s, pl: order.append(s.id) or "x").execute(p)
        assert order == [1, 2, 3]

    def test_diamond_dependency(self):
        order = []
        p = plan((1, []), (2, [1]), (3, [1]), (4, [2, 3]))
        PlanExecutor(lambda s, pl: order.append(s.id) or "x").execute(p)
        assert order[0] == 1 and order[-1] == 4
        assert set(order[1:3]) == {2, 3}

    def test_output_lists_completed_steps(self):
        run = PlanExecutor(ok).execute(plan((1, []), (2, [])))
        assert "1. step 1: result-1" in run.output
        assert "2. step 2: result-2" in run.output

    def test_on_step_callback(self):
        seen = []
        PlanExecutor(ok, on_step=seen.append).execute(plan((1, []), (2, [])))
        assert [s.id for s in seen] == [1, 2]

    def test_empty_plan(self):
        run = PlanExecutor(ok).execute(Plan(goal="g"))
        assert run.succeeded
        assert run.output == ""


class TestFailures:
    def test_a_raising_step_fails_the_step_not_the_run(self):
        def boom(step, p):
            raise RuntimeError("nope")

        run = PlanExecutor(boom).execute(plan((1, [])))
        assert not run.succeeded
        assert run.plan.get(1).status is StepStatus.FAILED
        assert "RuntimeError" in run.plan.get(1).result

    def test_execute_never_raises(self):
        def boom(step, p):
            raise KeyError("x")

        PlanExecutor(boom).execute(plan((1, []), (2, [1])))  # must not raise

    def test_dependents_are_skipped_not_hung(self):
        def boom_on_one(step, p):
            if step.id == 1:
                raise RuntimeError("nope")
            return "ok"

        run = PlanExecutor(boom_on_one, max_rounds=5).execute(plan((1, []), (2, [1])))
        assert run.plan.get(2).status is StepStatus.SKIPPED
        assert run.rounds < 5, "a failed dependency must not spin the executor"

    def test_independent_steps_still_run_after_a_failure(self):
        def boom_on_one(step, p):
            if step.id == 1:
                raise RuntimeError("nope")
            return "ok"

        run = PlanExecutor(boom_on_one).execute(plan((1, []), (2, []), (3, [1])))
        assert run.plan.get(2).status is StepStatus.DONE
        assert run.plan.get(3).status is StepStatus.SKIPPED

    def test_partial_output_is_returned(self):
        def boom_on_two(step, p):
            if step.id == 2:
                raise RuntimeError("nope")
            return f"result-{step.id}"

        run = PlanExecutor(boom_on_two).execute(plan((1, []), (2, [])))
        assert "result-1" in run.output


class TestLimits:
    def test_max_rounds_stops_a_stuck_executor(self):
        # a plan with an unsatisfiable dependency, built by hand to dodge the
        # parse-time repairs
        p = Plan(goal="g", steps=[PlanStep(id=1, description="a", depends_on=[99])])
        run = PlanExecutor(ok, max_rounds=3).execute(p)
        assert not run.succeeded
        assert run.error

    def test_no_runnable_steps_is_reported(self):
        p = Plan(goal="g", steps=[PlanStep(id=1, description="a", depends_on=[99])])
        run = PlanExecutor(ok).execute(p)
        assert run.error and "runnable" in run.error


class TestReplanning:
    def test_replan_fires_when_stuck(self):
        calls = []

        def replan(old):
            calls.append(old)
            return plan((1, []))

        stuck = Plan(goal="g", steps=[PlanStep(id=1, description="a", depends_on=[99])])
        run = PlanExecutor(ok, replan=replan).execute(stuck)
        assert len(calls) == 1
        assert run.replans == 1
        assert run.succeeded, "the replacement plan should have run"

    def test_replan_is_capped(self):
        calls = []

        def replan(old):
            calls.append(old)
            return Plan(goal="g", steps=[PlanStep(id=1, description="a",
                                                  depends_on=[99])])

        stuck = Plan(goal="g", steps=[PlanStep(id=1, description="a", depends_on=[99])])
        run = PlanExecutor(ok, replan=replan, max_replans=2).execute(stuck)
        assert len(calls) == 2, "unlimited replanning is the most expensive no-op there is"
        assert not run.succeeded

    def test_no_replan_configured(self):
        stuck = Plan(goal="g", steps=[PlanStep(id=1, description="a", depends_on=[99])])
        run = PlanExecutor(ok).execute(stuck)
        assert run.replans == 0

    def test_run_plan_points_at_the_new_plan(self):
        replacement = plan((1, []))
        stuck = Plan(goal="g", steps=[PlanStep(id=1, description="a", depends_on=[99])])
        run = PlanExecutor(ok, replan=lambda old: replacement).execute(stuck)
        assert run.plan is replacement


class TestPlanRun:
    def test_succeeded_requires_no_failures(self):
        p = plan((1, []))
        p.get(1).status = StepStatus.FAILED
        assert not PlanRun(plan=p).succeeded

    def test_succeeded_requires_completeness(self):
        assert not PlanRun(plan=plan((1, []))).succeeded
