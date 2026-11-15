"""Multi-agent patterns — and the machinery to know when you needed one.

Promoted from Chapter 8.

Read the chapter's opening before reaching for any of this. Most multi-agent systems
are single-agent problems with a coordination bug bolted on.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

# ------------------------------------------------------------------ blackboard


@dataclass
class Entry:
    """One write to the blackboard. The log is what makes a multi-agent run
    debuggable — without it you have several agents and no idea who did what."""

    key: str
    value: Any
    by: str
    at: float = field(default_factory=time.time)


class Blackboard:
    """Thread-safe shared state with an append-only audit log.

    The "blackboard" pattern: agents do not message each other, they read and write
    a shared surface. That decoupling is the point — an agent does not need to know
    who produced a fact or who will consume it.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._log: list[Entry] = []
        self._lock = threading.Lock()

    def write(self, key: str, value: Any, *, by: str = "unknown") -> None:
        with self._lock:
            self._values[key] = value
            self._log.append(Entry(key=key, value=value, by=by))

    def read(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._values

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    @property
    def log(self) -> list[Entry]:
        with self._lock:
            return list(self._log)

    def history(self, key: str) -> list[Entry]:
        """Every write to one key, oldest first. Shows overwrites — which is how you
        find two agents fighting over the same slot."""
        with self._lock:
            return [e for e in self._log if e.key == key]

    def render(self, *, max_chars: int = 400) -> str:
        """Blackboard contents for a prompt."""
        with self._lock:
            if not self._values:
                return "(nothing on the blackboard yet)"
            return "\n".join(
                f"- {key}: {str(value)[:max_chars]}"
                for key, value in self._values.items()
            )


# --------------------------------------------------------------------- routing


@dataclass
class Route:
    name: str
    description: str
    when_not: str = ""   # the single most effective field in this dataclass


class Router:
    """Pick one specialist for a request.

    The cheapest useful multi-agent pattern, and often the only one you need: one
    small model decides which prompt+toolset handles the request, and nothing else
    about the system is distributed.
    """

    def __init__(self, routes: list[Route], *, default: str | None = None) -> None:
        if not routes:
            raise ValueError("a router needs at least one route")
        self.routes = {r.name: r for r in routes}
        self.default = default or routes[0].name

    def prompt(self, query: str) -> str:
        lines = ["Route this request to exactly one handler.\n"]
        for route in self.routes.values():
            lines.append(f"- {route.name}: {route.description}")
            if route.when_not:
                lines.append(f"    do NOT use for: {route.when_not}")
        lines.append(f"\nREQUEST: {query}")
        lines.append("\nReply with the handler name and nothing else.")
        return "\n".join(lines)

    def parse(self, raw: str) -> str:
        """Map a model's answer to a route name. Unrecognised -> the default.

        Matches case-insensitively and accepts the name embedded in a sentence,
        because models say "I'd route this to billing" about a third of the time
        however firmly you ask for one word.
        """
        text = (raw or "").strip().lower()
        for name in self.routes:
            if name.lower() == text:
                return name
        for name in self.routes:
            if name.lower() in text:
                return name
        return self.default

    def route(self, query: str, call_model: Callable[[str], str]) -> str:
        return self.parse(call_model(self.prompt(query)))


@dataclass
class Handoff:
    """One agent passing control to another.

    `context` is the part people leave out, and leaving it out is why handoffs fail:
    the receiving agent starts from nothing and asks the user to repeat themselves.
    """

    target: str
    reason: str = ""
    context: str = ""

    def describe(self) -> str:
        return f"-> {self.target}" + (f": {self.reason}" if self.reason else "")


# ---------------------------------------------------------------- orchestration


@dataclass
class WorkerResult:
    name: str
    task: str
    output: str = ""
    error: str | None = None
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


class Orchestrator:
    """Fan out independent subtasks to workers, gather the results, synthesise.

    Workers are `Callable[[str], str]`. They can be agents, chains, or plain
    functions — the orchestrator does not care, which is what makes it testable.
    """

    def __init__(
        self,
        workers: dict[str, Callable[[str], str]],
        *,
        max_parallel: int = 4,
        on_result: Callable[[WorkerResult], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.workers = workers
        self.max_parallel = max_parallel
        self.on_result = on_result
        self.clock = clock

    def run_one(self, name: str, task: str) -> WorkerResult:
        worker = self.workers.get(name)
        if worker is None:
            return WorkerResult(name=name, task=task,
                                error=f"no worker named {name!r}")
        started = self.clock()
        try:
            output = worker(task)
        except Exception as exc:  # noqa: BLE001 - one worker must not kill the run
            return WorkerResult(name=name, task=task, error=f"{type(exc).__name__}: {exc}",
                                duration_s=self.clock() - started)
        return WorkerResult(name=name, task=task, output=str(output),
                            duration_s=self.clock() - started)

    def fan_out(self, assignments: list[tuple[str, str]]) -> list[WorkerResult]:
        """Run (worker_name, task) pairs concurrently. Results keep input order.

        A failing worker produces a WorkerResult with `error` set, never an
        exception. Partial results are worth far more than none: three of four
        research subtasks succeeding is a usable answer with a caveat.
        """
        if not assignments:
            return []
        if len(assignments) == 1 or self.max_parallel <= 1:
            results = [self.run_one(name, task) for name, task in assignments]
        else:
            with ThreadPoolExecutor(
                max_workers=min(self.max_parallel, len(assignments))
            ) as pool:
                results = list(pool.map(lambda a: self.run_one(*a), assignments))
        if self.on_result is not None:
            for result in results:
                self.on_result(result)
        return results


def synthesis_prompt(goal: str, results: list[WorkerResult]) -> str:
    """Build the synthesiser's input from worker outputs.

    Failures are INCLUDED, labelled. A synthesiser that cannot see that the pricing
    research failed will happily write a confident paragraph about pricing.
    """
    lines = [f"GOAL: {goal}", "", "Findings from each worker:"]
    for result in results:
        lines.append(f"\n--- {result.name} ---")
        lines.append(result.output if result.ok else f"[FAILED: {result.error}]")
    lines.append(
        "\nWrite a single coherent answer to the goal using only the findings above. "
        "Where a worker failed, say what is missing rather than guessing."
    )
    return "\n".join(lines)
