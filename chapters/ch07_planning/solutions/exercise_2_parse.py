"""SOLUTION — Chapter 7, Exercise 2."""

from __future__ import annotations

import json
from typing import Any

from .exercise_1_plan import Plan, PlanStep


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
    items = json_array(raw)
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


def json_array(raw: str) -> list[Any]:
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
