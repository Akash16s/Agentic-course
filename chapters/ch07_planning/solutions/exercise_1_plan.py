"""SOLUTION — Chapter 7, Exercise 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """One unit of work in a plan."""

    id: int
    description: str
    depends_on: list[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str = ""

    @property
    def finished(self) -> bool:
        return self.status in (StepStatus.DONE, StepStatus.FAILED, StepStatus.SKIPPED)


@dataclass
class Plan:
    """An ordered set of steps with dependencies."""

    goal: str
    steps: list[PlanStep] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.steps)

    def get(self, step_id: int) -> PlanStep | None:
        return next((s for s in self.steps if s.id == step_id), None)

    @property
    def complete(self) -> bool:
        return all(s.finished for s in self.steps)

    @property
    def failed(self) -> bool:
        return any(s.status is StepStatus.FAILED for s in self.steps)

    def ready_steps(self) -> list[PlanStep]:
        """Pending steps whose dependencies are all DONE.

        Returns several when they are independent — those can run in parallel.
        A step whose dependency FAILED is not ready and never will be; `skip_blocked`
        handles it.
        """
        done = {s.id for s in self.steps if s.status is StepStatus.DONE}
        return [
            s for s in self.steps
            if s.status is StepStatus.PENDING and all(d in done for d in s.depends_on)
        ]

    def skip_blocked(self) -> list[PlanStep]:
        """Mark every step that can never run (a dependency failed or was skipped).

        Without this the executor stalls: nothing is ready, nothing is finished, and
        the loop spins until its step budget runs out with no explanation.
        """
        dead = {
            s.id for s in self.steps
            if s.status in (StepStatus.FAILED, StepStatus.SKIPPED)
        }
        skipped: list[PlanStep] = []
        changed = True
        while changed:
            changed = False
            for step in self.steps:
                if step.status is not StepStatus.PENDING:
                    continue
                if any(d in dead for d in step.depends_on):
                    step.status = StepStatus.SKIPPED
                    step.result = "skipped: a dependency did not complete"
                    dead.add(step.id)
                    skipped.append(step)
                    changed = True
        return skipped

    def render(self) -> str:
        """Human- and model-readable plan state. Goes back into the prompt."""
        marks = {
            StepStatus.PENDING: "[ ]",
            StepStatus.RUNNING: "[~]",
            StepStatus.DONE: "[x]",
            StepStatus.FAILED: "[!]",
            StepStatus.SKIPPED: "[-]",
        }
        lines = [f"GOAL: {self.goal}"]
        for step in self.steps:
            deps = f" (after {', '.join(map(str, step.depends_on))})" if step.depends_on else ""
            lines.append(f"{marks[step.status]} {step.id}. {step.description}{deps}")
            if step.result:
                lines.append(f"      -> {step.result[:160]}")
        return "\n".join(lines)
