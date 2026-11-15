"""EXERCISE 2 — Stop conditions, in isolation.

WHY: Pulling the exit logic out of the loop makes it testable, which matters because
these are the conditions that decide whether a bug costs you $0.02 or $200. Frameworks
bury this; you should be able to read it in one screen.

    pytest chapters/ch03_react_loop/tests -q -k stop
"""

from __future__ import annotations

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
    """Should the loop stop BEFORE making another model call?

    Returns the reason, or None to continue.

    Spec — check in this priority order:
      1. budget_usd is not None and spent_usd >= budget_usd  -> StopReason.BUDGET
      2. timeout_s is not None and elapsed_s >= timeout_s    -> StopReason.TIMEOUT
      3. len(steps) >= max_steps                             -> StopReason.MAX_STEPS
      4. otherwise                                           -> None

    Why budget first: it is the condition with real-world consequences. If two limits
    are hit at once, you want the log to say "we ran out of money", because that is the
    one someone has to act on.

    Note `>=`, not `>`. With max_steps=3 and 3 steps already taken, you are done —
    an off-by-one here means every agent you ship runs one step more than configured.

    >>> check_stop_conditions([], max_steps=5) is None
    True
    >>> check_stop_conditions([], max_steps=0)
    <StopReason.MAX_STEPS: 'max_steps'>
    """
    # TODO: implement
    raise NotImplementedError


def detect_repetition(steps: list[Step], *, window: int = 3) -> bool:
    """True if the last `window` steps all made the IDENTICAL single tool call.

    "Identical" = same tool name AND same arguments. Normalise arguments to a
    comparable form first: a dict and its JSON string are the same call.

    Spec:
      * fewer than `window` steps -> False
      * any of the last `window` steps has != 1 tool call -> False
      * all `window` calls share name and normalised arguments -> True

    This catches the most common pathology — the repeater — while it is happening,
    so the loop can inject a nudge instead of burning 20 more steps. Chapter 7 uses
    this to trigger reflection.

    Keep `window` at 3: two identical calls in a row is sometimes legitimate (retrying
    after a transient failure); three is always a bug.
    """
    # TODO: implement
    raise NotImplementedError
