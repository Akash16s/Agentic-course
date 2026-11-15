"""EXERCISE 1 — Cases and datasets.

    pytest chapters/ch10_evals_basics/tests -q -k dataset
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable


@dataclass
class EvalCase:
    """One test.

    Fields: id: str, input: str, expected: Any = None,
            tags: list[str] = [], metadata: dict = {}

    `expected` is deliberately untyped. Sometimes it is a string to match, sometimes
    a list of required phrases, sometimes a tool name, sometimes a whole object.
    Pinning it down would just mean fighting the type later.
    """

    id: str
    input: str
    expected: Any = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Dataset:
    """A named set of cases.

    JSONL, not JSON. You can append a case without rewriting the file, diff it line
    by line in review, and stream it if it grows. Eval datasets are hand-edited far
    more often than people expect, and that is what decides the format.
    """

    def __init__(self, cases: Iterable[EvalCase] = (), *, name: str = "dataset") -> None:
        # TODO: implement
        raise NotImplementedError

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

    def __iter__(self):
        """Iterate the cases, so `for case in dataset` works."""
        # TODO: implement
        raise NotImplementedError

    def filter(
        self,
        *,
        tag: str | None = None,
        predicate: Callable[[EvalCase], bool] | None = None,
    ) -> "Dataset":
        """A NEW Dataset with the matching cases.

        Both filters apply when both are given. Name the result
        f"{self.name}[filtered]" so a report says where it came from.
        """
        # TODO: implement
        raise NotImplementedError

    @classmethod
    def from_jsonl(cls, path: str, *, name: str | None = None) -> "Dataset":
        """Load from JSONL.

        Spec:
          * one JSON object per line
          * SKIP blank lines and lines starting with "//" (people comment their
            eval files; a loader that crashes on a comment is a loader people work
            around)
          * `id` defaults to the 1-based line number
          * `input` is required — let a KeyError surface, because a case with no
            input is a broken file, not a tolerable one
          * expected/tags/metadata default to None/[]/{}
          * `name` defaults to `path`
        """
        # TODO: implement
        raise NotImplementedError

    def to_jsonl(self, path: str) -> None:
        """Write one `json.dumps(asdict(case))` per line."""
        # TODO: implement
        raise NotImplementedError
