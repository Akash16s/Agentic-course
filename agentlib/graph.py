"""A state graph in ~150 lines — i.e. most of what LangGraph is.

Promoted from Chapter 17.

Building this is the point of the chapter. Once you have written `invoke`, reading
LangGraph's source is an afternoon rather than a project, and you can tell which of
its features you actually need.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

START = "__start__"
END = "__end__"

#: A node takes the state and returns a PARTIAL update — the keys it changed.
#: Returning a partial rather than the whole state is what makes nodes composable:
#: a node that only knows about `messages` never has to know the rest exists.
Node = Callable[[dict[str, Any]], dict[str, Any]]

#: A router looks at the state and names the next node.
Router = Callable[[dict[str, Any]], str]

#: A reducer says how to merge an update into existing state.
Reducer = Callable[[Any, Any], Any]


def replace(current: Any, update: Any) -> Any:
    """Default reducer: the update wins."""
    return update


def append(current: Any, update: Any) -> Any:
    """Accumulate lists. This is how `messages` works in every graph framework.

    Without it, every node that touches `messages` would have to read the whole
    list, copy it, append, and return it — and any node that forgot would silently
    wipe the conversation.
    """
    if current is None:
        return list(update) if isinstance(update, list) else [update]
    if isinstance(update, list):
        return list(current) + update
    return list(current) + [update]


def add(current: Any, update: Any) -> Any:
    """Accumulate numbers — step counts, costs, token totals."""
    return (current or 0) + update


class GraphError(Exception):
    pass


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


class StateGraph:
    """Nodes, edges, and a shared state dict. That is the whole model.

    >>> graph = StateGraph({"messages": append})
    >>> graph.add_node("think", think)
    >>> graph.add_node("act", act)
    >>> graph.set_entry("think")
    >>> graph.add_conditional_edges("think", route, {"act": "act", "done": END})
    >>> graph.add_edge("act", "think")
    >>> result = graph.compile().invoke({"messages": []})
    """

    def __init__(self, reducers: dict[str, Reducer] | None = None) -> None:
        #: key -> how to merge updates for that key. Anything unlisted is replaced.
        self.reducers = dict(reducers or {})
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, str] = {}
        self.conditional: dict[str, tuple[Router, dict[str, str]]] = {}
        self.entry: str | None = None

    # ------------------------------------------------------------ building

    def add_node(self, name: str, node: Node) -> "StateGraph":
        if name in (START, END):
            raise GraphError(f"{name!r} is reserved")
        if name in self.nodes:
            raise GraphError(f"node {name!r} already exists")
        self.nodes[name] = node
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        """An unconditional edge. `source` always goes to `target`."""
        if source in self.conditional:
            raise GraphError(f"{source!r} already has conditional edges")
        self.edges[source] = target
        return self

    def add_conditional_edges(self, source: str, router: Router,
                              mapping: dict[str, str]) -> "StateGraph":
        """Branch on a router's return value.

        The router returns a KEY, and the mapping turns it into a node name. The
        indirection looks redundant until you want to rewire a graph without
        touching the routing logic — which is exactly what you do when you add a
        step.
        """
        if source in self.edges:
            raise GraphError(f"{source!r} already has an unconditional edge")
        self.conditional[source] = (router, dict(mapping))
        return self

    def set_entry(self, name: str) -> "StateGraph":
        self.entry = name
        return self

    # ---------------------------------------------------------- validation

    def validate(self) -> None:
        """Catch the graph mistakes that would otherwise be runtime hangs.

        Every check here exists because the failure it prevents presents as a
        confusing stall or a KeyError three nodes later, rather than as a message
        about the thing you got wrong.
        """
        if self.entry is None:
            raise GraphError("no entry point; call set_entry()")
        if self.entry not in self.nodes:
            raise GraphError(f"entry {self.entry!r} is not a node")

        for source, target in self.edges.items():
            if source not in self.nodes:
                raise GraphError(f"edge from unknown node {source!r}")
            if target not in self.nodes and target != END:
                raise GraphError(f"edge to unknown node {target!r}")

        for source, (_, mapping) in self.conditional.items():
            if source not in self.nodes:
                raise GraphError(f"conditional edge from unknown node {source!r}")
            for key, target in mapping.items():
                if target not in self.nodes and target != END:
                    raise GraphError(
                        f"conditional edge {source!r}[{key!r}] -> unknown {target!r}")

        for name in self.nodes:
            if name not in self.edges and name not in self.conditional:
                raise GraphError(
                    f"node {name!r} has no outgoing edge; it would stall the graph")

    def compile(self) -> "CompiledGraph":
        self.validate()
        return CompiledGraph(self)

    # ---------------------------------------------------------------- misc

    def to_mermaid(self) -> str:
        """A Mermaid diagram. Being able to SEE the graph is most of why people
        reach for a graph framework in the first place."""
        lines = ["graph TD"]
        lines.append(f"    {START}([start]) --> {self.entry}")
        for source, target in self.edges.items():
            lines.append(f"    {source} --> {target}")
        for source, (_, mapping) in self.conditional.items():
            for key, target in mapping.items():
                lines.append(f"    {source} -->|{key}| {target}")
        return "\n".join(lines)


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
