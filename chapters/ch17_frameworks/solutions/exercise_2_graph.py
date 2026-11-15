"""SOLUTION — Chapter 17, Exercise 2."""

from __future__ import annotations

from typing import Any, Callable

from .exercise_1_reducers import END, START, replace

Node = Callable[[dict[str, Any]], dict[str, Any]]
Router = Callable[[dict[str, Any]], str]
Reducer = Callable[[Any, Any], Any]


class GraphError(Exception):
    pass



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

    def compile(self):
        from .exercise_3_execution import CompiledGraph

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
