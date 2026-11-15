"""Requirement 10 + 11: the checks your dataset is scored with."""

from __future__ import annotations

from agentlib.evals.core import (
    Check,
    expected_contains,
    max_cost,
    max_steps,
    succeeded,
    tool_called,
    tool_not_called,
)
from agentlib.evals.judge import LLMJudge, trajectory_contains

RUBRIC = """\
TODO: anchor EVERY point to something observable.

5 = ...
4 = ...
3 = ...
2 = ...
1 = ...

CALIBRATE THIS BEFORE YOU TRUST IT. Grade five responses yourself, then have the
judge grade the same five. Keep editing until you agree on at least four. An
uncalibrated rubric is a random number generator with good manners.
"""


def build_checks(judge_model) -> list[Check]:
    """The checks every case is scored with.

    Include at minimum:
        expected_contains()
        succeeded()
        max_steps(...)
        max_cost(...)
        tool_not_called("<your irreversible tool>")   <- on EVERY case
        trajectory_contains([...])                     <- ch 11
        LLMJudge(RUBRIC, judge_model).as_check()       <- ch 11

    Use a DIFFERENT model for the judge than the one being graded. Models flatter
    their own output, and it flatters exactly the thing you are measuring.
    """
    raise NotImplementedError
