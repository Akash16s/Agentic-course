"""SOLUTION — Chapter 17, Exercise 3."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterator

from .exercise_1_reducers import END, replace
from .exercise_2_graph import GraphError, StateGraph


@dataclass
class Step:
    """One node execution. The graph's own trace."""

    node: str
    update: dict[str, Any]
    state: dict[str, Any]


@dataclass
class GraphResult:
    state: dict[str, Any]
    steps: list[Step] = field(default_factory=list)
    stopped_early: bool = False

    @property
    def path(self) -> list[str]:
        return [s.node for s in self.steps]

class CompiledGraph:
    """A validated graph you can run."""

    def __init__(self, graph: StateGraph) -> None:
        self.graph = graph

    def _merge(self, state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(state)
        for key, value in (update or {}).items():
            reducer = self.graph.reducers.get(key, replace)
            merged[key] = reducer(merged.get(key), value)
        return merged

    def _next(self, node: str, state: dict[str, Any]) -> str:
        if node in self.graph.conditional:
            router, mapping = self.graph.conditional[node]
            key = router(state)
            if key not in mapping:
                raise GraphError(
                    f"router at {node!r} returned {key!r}, "
                    f"which is not in {sorted(mapping)}")
            return mapping[key]
        return self.graph.edges[node]

    def stream(self, state: dict[str, Any], *,
               max_steps: int = 50) -> Iterator[Step]:
        """Run, yielding each step. `invoke` is this, drained.

        A bounded `for`, exactly as in Chapter 3: a graph with a cycle and a
        router that never says "done" is the same infinite loop wearing a diagram.
        """
        current = self.graph.entry
        state = copy.deepcopy(state)

        for _ in range(max_steps):
            if current == END:
                return
            node = self.graph.nodes[current]
            update = node(state) or {}
            state = self._merge(state, update)
            yield Step(node=current, update=update, state=copy.deepcopy(state))
            current = self._next(current, state)

    def invoke(self, state: dict[str, Any], *,
               max_steps: int = 50) -> GraphResult:
        steps = list(self.stream(state, max_steps=max_steps))
        final = steps[-1].state if steps else copy.deepcopy(state)
        stopped_early = len(steps) >= max_steps
        return GraphResult(state=final, steps=steps, stopped_early=stopped_early)
