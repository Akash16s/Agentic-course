"""SOLUTION — Chapter 3, Exercise 2."""

from __future__ import annotations

import json

from .exercise_1_result import StopReason, Step


def check_stop_conditions(
    steps: list[Step],
    *,
    max_steps: int,
    elapsed_s: float = 0.0,
    timeout_s: float | None = None,
    spent_usd: float = 0.0,
    budget_usd: float | None = None,
) -> StopReason | None:
    # Money first: it is the limit a human has to act on.
    if budget_usd is not None and spent_usd >= budget_usd:
        return StopReason.BUDGET
    if timeout_s is not None and elapsed_s >= timeout_s:
        return StopReason.TIMEOUT
    if len(steps) >= max_steps:
        return StopReason.MAX_STEPS
    return None


def _normalise(arguments) -> str:
    """A dict and its JSON string are the same call. Compare a canonical form."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            return arguments
    try:
        return json.dumps(arguments, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(arguments)


def detect_repetition(steps: list[Step], *, window: int = 3) -> bool:
    if len(steps) < window:
        return False

    recent = steps[-window:]
    if any(len(step.tool_calls) != 1 for step in recent):
        return False

    signatures = {
        (step.tool_calls[0].name, _normalise(step.tool_calls[0].arguments))
        for step in recent
    }
    return len(signatures) == 1
