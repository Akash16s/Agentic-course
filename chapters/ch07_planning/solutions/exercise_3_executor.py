"""SOLUTION — Chapter 7, Exercise 3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .exercise_1_plan import Plan, PlanStep, StepStatus


@dataclass
class PlanRun:
    plan: Plan
    output: str = ""
    rounds: int = 0
    replans: int = 0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.plan.complete and not self.plan.failed


class PlanExecutor:
    """Run a plan step by step, optionally re-planning when things go wrong.

    `run_step(step, plan)` does the actual work and returns a result string, or
    raises to mark the step failed. It is injected rather than baked in so this class
    knows nothing about agents, models or tools — which is what makes it testable.
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
        self.run_step = run_step
        self.max_rounds = max_rounds
        self.replan = replan
        self.max_replans = max_replans
        self.on_step = on_step

    def execute(self, plan: Plan) -> PlanRun:
        run = PlanRun(plan=plan)

        while not plan.complete and run.rounds < self.max_rounds:
            run.rounds += 1
            ready = plan.ready_steps()

            if not ready:
                # nothing runnable: either blocked by failures, or a bad plan
                if plan.skip_blocked():
                    continue
                if self.replan and run.replans < self.max_replans:
                    run.replans += 1
                    plan = self.replan(plan)
                    run.plan = plan
                    continue
                run.error = "no runnable steps remain"
                break

            for step in ready:
                step.status = StepStatus.RUNNING
                try:
                    step.result = self.run_step(step, plan)
                    step.status = StepStatus.DONE
                except Exception as exc:  # noqa: BLE001 - a bad step is not a bad run
                    step.status = StepStatus.FAILED
                    step.result = f"{type(exc).__name__}: {exc}"
                if self.on_step is not None:
                    self.on_step(step)

            plan.skip_blocked()

        if not plan.complete and run.error is None:
            run.error = f"stopped after {run.rounds} rounds with steps outstanding"

        run.output = "\n".join(
            f"{s.id}. {s.description}: {s.result}"
            for s in plan.steps
            if s.status is StepStatus.DONE
        )
        return run
