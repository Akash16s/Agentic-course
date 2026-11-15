"""EXERCISE 1 — State reducers.

    pytest chapters/ch17_frameworks/tests -q -k reducers
"""

from __future__ import annotations

from typing import Any

START = "__start__"
END = "__end__"


def replace(current: Any, update: Any) -> Any:
    """The default: the update wins outright."""
    # TODO: implement
    raise NotImplementedError


def append(current: Any, update: Any) -> Any:
    """Accumulate into a list. This is how `messages` works in every graph
    framework, and it is the reducer that justifies the whole concept.

    Spec:
      * current is None  -> list(update) if update is a list, else [update]
      * update is a list -> current + update
      * otherwise        -> current + [update]

    Always return a NEW list; never mutate `current`. A node that mutates shared
    state produces the kind of bug where replaying a run gives a different answer.

    WITHOUT THIS, every node that touches `messages` has to read the whole list,
    copy it, append and return it — and any node that forgets silently wipes the
    conversation. The reducer moves that responsibility to one place.
    """
    # TODO: implement
    raise NotImplementedError


def add(current: Any, update: Any) -> Any:
    """Accumulate numbers: step counts, costs, token totals.

    `(current or 0) + update`, so a missing key starts at zero.
    """
    # TODO: implement
    raise NotImplementedError
