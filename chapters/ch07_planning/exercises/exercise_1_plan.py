"""EXERCISE 1 — The plan data structure.

    pytest chapters/ch07_planning/tests -q -k plan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepStatus(str, Enum):
    """PENDING, RUNNING, DONE, FAILED, SKIPPED — values are the lowercase names."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """One unit of work.

    Fields: id: int, description: str, depends_on: list[int] = [],
            status: StepStatus = PENDING, result: str = ""
    """

    id: int
    description: str
    depends_on: list[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str = ""

    @property
    def finished(self) -> bool:
        """True for DONE, FAILED and SKIPPED.

        Note FAILED counts as finished. A plan where every step has *resolved* is
        complete even if some resolved badly — 'complete' and 'succeeded' are
        different questions.
        """
        # TODO: implement
        raise NotImplementedError


@dataclass
class Plan:
    """A goal plus ordered steps with dependencies.

    Fields: goal: str, steps: list[PlanStep] = []
    """

    goal: str
    steps: list[PlanStep] = field(default_factory=list)

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

    def get(self, step_id: int) -> PlanStep | None:
        # TODO: implement
        raise NotImplementedError

    @property
    def complete(self) -> bool:
        """Every step finished (in any terminal state)."""
        # TODO: implement
        raise NotImplementedError

    @property
    def failed(self) -> bool:
        """Any step FAILED."""
        # TODO: implement
        raise NotImplementedError

    def ready_steps(self) -> list[PlanStep]:
        """Every PENDING step whose dependencies are all DONE.

        RETURNS A LIST, NOT ONE STEP. Everything in it is independent and will be run
        concurrently — returning a single step silently throws away the only real
        performance advantage a plan has over a reactive loop.

        A step depending on a FAILED step is not ready (and never will be);
        `skip_blocked` deals with it.
        """
        # TODO: implement
        raise NotImplementedError

    def skip_blocked(self) -> list[PlanStep]:
        """Mark every step that can never run. Return the ones newly skipped.

        A step is blocked if any dependency is FAILED or SKIPPED. Skipping must
        CASCADE: if 1 fails, 2 depends on 1 and 3 depends on 2, all of 2 and 3 are
        dead. Loop until nothing changes.

        Without this the executor stalls: nothing is ready, nothing new finishes, and
        it spins until the round budget runs out. It presents as a hang, not an
        error, which is the worst kind of bug to diagnose.

        Set `result` to something explanatory on each skipped step.
        """
        # TODO: implement
        raise NotImplementedError

    def render(self) -> str:
        """Plan state as text, for the prompt and for humans.

        Suggested format:
            GOAL: <goal>
            [x] 1. read the config
                  -> found timeout=30
            [ ] 2. compare settings (after 1)

        markers: PENDING '[ ]', RUNNING '[~]', DONE '[x]', FAILED '[!]', SKIPPED '[-]'
        Truncate each result to ~160 chars — this goes into a context window.
        """
        # TODO: implement
        raise NotImplementedError
