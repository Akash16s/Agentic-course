"""SOLUTION — Chapter 10, Exercise 1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable


@dataclass
class EvalCase:
    """One test. `expected` is free-form: whatever your checks need."""

    id: str
    input: str
    expected: Any = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Dataset:
    """A named set of eval cases, loadable from JSONL.

    JSONL rather than JSON: you can append a case without rewriting the file, diff
    it line by line in review, and stream it if it gets big. Eval datasets are
    edited by hand far more often than people expect, and that decides the format.
    """

    def __init__(self, cases: Iterable[EvalCase] = (), *, name: str = "dataset") -> None:
        self.name = name
        self.cases = list(cases)

    def __len__(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def filter(self, *, tag: str | None = None,
               predicate: Callable[[EvalCase], bool] | None = None) -> "Dataset":
        cases = self.cases
        if tag is not None:
            cases = [c for c in cases if tag in c.tags]
        if predicate is not None:
            cases = [c for c in cases if predicate(c)]
        return Dataset(cases, name=f"{self.name}[filtered]")

    @classmethod
    def from_jsonl(cls, path: str, *, name: str | None = None) -> "Dataset":
        cases: list[EvalCase] = []
        with open(path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                row = json.loads(line)
                cases.append(
                    EvalCase(
                        id=str(row.get("id", line_number)),
                        input=row["input"],
                        expected=row.get("expected"),
                        tags=list(row.get("tags", [])),
                        metadata=row.get("metadata", {}),
                    )
                )
        return cls(cases, name=name or path)

    def to_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            for case in self.cases:
                handle.write(json.dumps(asdict(case)) + "\n")
