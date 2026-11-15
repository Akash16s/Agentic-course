"""EXERCISE 3 — Running the graph.

    pytest chapters/ch17_frameworks/tests -q -k execution
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterator

from .exercise_1_reducers import END, replace
from .exercise_2_graph import GraphError, StateGraph


@dataclass
class Step:
    """node: str, update: dict, state: dict (a snapshot AFTER merging)."""

    node: str
    update: dict[str, Any]
    state: dict[str, Any]


@dataclass
class GraphResult:
    """state: dict, steps: list[Step] = [], stopped_early: bool = False"""

    state: dict[str, Any]

    @property
    def path(self) -> list[str]:
        """The node names, in execution order. The graph's `tool_sequence`."""
        # TODO: implement
        raise NotImplementedError


class CompiledGraph:
    """A validated graph you can run."""

    def __init__(self, graph: StateGraph) -> None:
        self.graph = graph

    def _merge(self, state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial update using the per-key reducers.

        Spec: start from a COPY of state; for each key in the update, look up
        `self.graph.reducers.get(key, replace)` and apply it to
        (existing value, update value).

        Copy, don't mutate: `stream` hands out state snapshots, and a caller that
        holds one must not see it change under them.
        """
        # TODO: implement
        raise NotImplementedError

    def _next(self, node: str, state: dict[str, Any]) -> str:
        """Which node runs next.

        Conditional: call the router, look its key up in the mapping. A key that
        is NOT in the mapping must raise GraphError naming the key and the valid
        options — silently falling through would stall the graph and the message
        would point nowhere.

        Otherwise: the unconditional edge.
        """
        # TODO: implement
        raise NotImplementedError

    def stream(self, state: dict[str, Any], *,
               max_steps: int = 50) -> Iterator[Step]:
        """Run the graph, yielding each Step.

        Spec:
            current = self.graph.entry
            state = deepcopy(state)          # never mutate the caller's dict
            for _ in range(max_steps):
                if current == END: return
                update = self.graph.nodes[current](state) or {}
                state = self._merge(state, update)
                yield Step(current, update, deepcopy(state))
                current = self._next(current, state)

        A BOUNDED `for`, exactly as in Chapter 3. A graph with a cycle and a
        router that never says "done" is the same infinite loop wearing a diagram.
        Drawing it does not make it terminate.

        `or {}` because a node that returns None is a node that changed nothing,
        not an error.
        """
        # TODO: implement
        raise NotImplementedError

    def invoke(self, state: dict[str, Any], *,
               max_steps: int = 50) -> GraphResult:
        """Drain `stream` into a GraphResult.

        `stopped_early` is True when the step budget ran out — the graph did not
        reach END. Treat it exactly like Chapter 3's MAX_STEPS: a signal, not a
        success.
        """
        # TODO: implement
        raise NotImplementedError
