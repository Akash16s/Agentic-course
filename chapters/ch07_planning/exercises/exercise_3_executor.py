"""EXERCISE 3 — Running a plan.

    pytest chapters/ch07_planning/tests -q -k executor
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .exercise_1_plan import Plan, PlanStep, StepStatus


@dataclass
class PlanRun:
    """The outcome of executing a plan.

    Fields: plan: Plan, output: str = "", rounds: int = 0, replans: int = 0,
            error: str | None = None
    """

    plan: Plan

    @property
    def succeeded(self) -> bool:
        """Complete AND nothing failed. 'Complete' alone is not success — a plan
        where every step failed is also complete."""
        # TODO: implement
        raise NotImplementedError


class PlanExecutor:
    """Run a plan to completion.

    __init__(self, run_step, *, max_rounds=20, replan=None, max_replans=1,
             on_step=None)

    `run_step(step, plan) -> str` does the work, or raises to fail the step. It is
    INJECTED, so this class knows nothing about models, tools or agents — which is
    exactly why it can be tested in microseconds.
    """

    def __init__(
        self,
        run_step: Callable[[PlanStep, Plan], str],
        *,
        max_rounds: int = 20,
        replan: Callable[[Plan], Plan] | None = None,
        max_replans: int = 1,
        on_step: Callable[[PlanStep], None] | None = None,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def execute(self, plan: Plan) -> PlanRun:
        """Algorithm:

        while not plan.complete and rounds < max_rounds:
            rounds += 1
            ready = plan.ready_steps()

            if not ready:
                # nothing runnable
                if plan.skip_blocked():        cascade failures, then retry
                    continue
                if replan and replans < max_replans:
                    replans += 1
                    plan = self.replan(plan);  run.plan = plan;  continue
                error = "no runnable steps remain";  break

            for step in ready:                 # all independent -> could be parallel
                step.status = RUNNING
                try:
                    step.result = self.run_step(step, plan)
                    step.status = DONE
                except Exception as exc:
                    step.status = FAILED
                    step.result = f"{type(exc).__name__}: {exc}"
                on_step(step) if on_step

            plan.skip_blocked()

        if not complete and no error: error = f"stopped after {rounds} rounds ..."

        output = the DONE steps, one per line: "{id}. {description}: {result}"

        NOTES:
          * catch Exception around run_step. A step that raises must fail the STEP,
            not the run — the rest of the plan may still be achievable, and
            `skip_blocked` will prune what isn't.
          * `max_rounds` is the backstop against a bug in your own readiness logic.
            Keep it even when you are sure you don't need it.
          * cap `max_replans` at 1-2. Unlimited re-planning is the most expensive way
            known to achieve nothing.
        """
        # TODO: implement
        raise NotImplementedError
