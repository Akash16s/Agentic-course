"""Planning and reflection — making the agent think before, and about, acting.

Promoted from Chapter 7.

Chapter 3's loop is purely reactive: one step at a time, no lookahead, no review.
That is right for short tasks and wrong for long ones. This adds the two classic
augmentations: decide the steps up front (plan-and-execute), and check your own work
(reflection).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from agentlib.llm import Message


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


# ----------------------------------------------------------------- planning

PLANNER_PROMPT = """\
Break this goal into the smallest number of concrete steps that actually achieves it.

GOAL: {goal}

{context}

Rules:
- Each step must be a single concrete action, not a vague intention.
  BAD:  "research the topic"
  GOOD: "read config/database.yml and note the connection timeout"
- Use `depends_on` only for real ordering constraints. Steps with no dependency
  between them will be run in parallel, so unnecessary dependencies cost you time.
- 3 to 7 steps. If it needs more than 7, the goal is too big; make the last step
  "re-plan with what we have learned".
- Do not include a step for reporting the answer. That happens automatically.

Return ONLY a JSON array:
[{{"id": 1, "description": "...", "depends_on": []}}, ...]"""


def parse_plan(goal: str, raw: str) -> Plan:
    """Build a Plan from a model's JSON. Never raises.

    Tolerates: markdown fences, prose either side, missing `depends_on`, string ids,
    and dependencies pointing at steps that do not exist (those are dropped — a
    dangling dependency would deadlock the executor forever).
    """
    items = _json_array(raw)
    steps: list[PlanStep] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            steps.append(PlanStep(id=index, description=item))
            continue
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("step") or "").strip()
        if not description:
            continue
        try:
            step_id = int(item.get("id", index))
        except (TypeError, ValueError):
            step_id = index
        depends = []
        for dep in item.get("depends_on") or []:
            try:
                depends.append(int(dep))
            except (TypeError, ValueError):
                continue
        steps.append(PlanStep(id=step_id, description=description, depends_on=depends))

    # drop dependencies on steps that do not exist, or the executor deadlocks
    known = {s.id for s in steps}
    for step in steps:
        step.depends_on = [d for d in step.depends_on if d in known and d != step.id]

    _break_cycles(steps)
    return Plan(goal=goal, steps=steps)


def _break_cycles(steps: list[PlanStep]) -> None:
    """Remove back-edges so the dependency graph is acyclic.

    A model asked for dependencies will occasionally produce 1->2->1. Nothing is ever
    ready, the executor stalls, and the failure looks like a hang rather than a bad
    plan. Cheaper to repair than to detect at runtime.
    """
    order = {step.id: index for index, step in enumerate(steps)}
    for step in steps:
        step.depends_on = [d for d in step.depends_on if order.get(d, -1) < order[step.id]]


def _json_array(raw: str) -> list[Any]:
    raw = (raw or "").strip()
    if "```" in raw:
        blocks = raw.split("```")
        raw = max(blocks, key=len)
        raw = raw.removeprefix("json").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(raw[start: end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


# --------------------------------------------------------------- reflection

CRITIC_PROMPT = """\
You are reviewing another assistant's work. Be specific and be hard to please, but do
not invent problems.

TASK: {task}

ANSWER:
{answer}

Judge only these:
1. Does it actually answer the task that was asked?
2. Is anything stated as fact that was not established by the work done?
3. Is anything required by the task missing?

Return ONLY JSON:
{{"acceptable": true/false, "issues": ["..."], "suggestion": "one concrete fix"}}

If it is acceptable, return an empty issues list. Do not pad."""


@dataclass
class Critique:
    acceptable: bool
    issues: list[str] = field(default_factory=list)
    suggestion: str = ""

    @property
    def summary(self) -> str:
        if self.acceptable:
            return "acceptable"
        return "; ".join(self.issues) or "unspecified problems"


def parse_critique(raw: str) -> Critique:
    """Parse a critic response. Unparseable output is treated as ACCEPTABLE.

    That default matters: if a broken critic meant "rejected", one malformed response
    would send the agent into an endless revision loop, which is both expensive and
    invisible. Failing open costs you one missed review.
    """
    obj = _json_object(raw)
    if obj is None:
        return Critique(acceptable=True)
    issues = [str(i) for i in (obj.get("issues") or []) if str(i).strip()]
    acceptable = bool(obj.get("acceptable", not issues))
    return Critique(
        acceptable=acceptable and not issues,
        issues=issues,
        suggestion=str(obj.get("suggestion", "")),
    )


def _json_object(raw: str) -> dict[str, Any] | None:
    raw = (raw or "").strip()
    if "```" in raw:
        raw = max(raw.split("```"), key=len).removeprefix("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start: end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def reflect_loop(
    task: str,
    produce: Callable[[str | None], str],
    criticise: Callable[[str, str], Critique],
    *,
    max_rounds: int = 3,
) -> tuple[str, list[Critique]]:
    """Produce, critique, revise — up to `max_rounds` times.

    `produce(feedback)` is called with None first, then with the critic's suggestion.
    Returns the final answer and every critique made along the way.

    WHEN THIS HELPS: verifiable work — code that must compile, output that must match
    a format, answers that must cite sources.

    WHEN IT DOES NOT: matters of taste, and anything the critic cannot actually check.
    A critic with no more information than the producer mostly generates plausible
    objections, and you pay 2-3x for a differently-worded answer. Measure it
    (Chapter 10) rather than assuming it helps.
    """
    critiques: list[Critique] = []
    answer = produce(None)
    for _ in range(max_rounds):
        critique = criticise(task, answer)
        critiques.append(critique)
        if critique.acceptable:
            break
        answer = produce(critique.suggestion or critique.summary)
    return answer, critiques


# ----------------------------------------------------------------- executor


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
