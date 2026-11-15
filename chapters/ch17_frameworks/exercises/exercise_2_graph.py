"""EXERCISE 2 — The graph: building and validating.

    pytest chapters/ch17_frameworks/tests -q -k graph
"""

from __future__ import annotations

from typing import Any, Callable

from .exercise_1_reducers import END, START, replace

Node = Callable[[dict[str, Any]], dict[str, Any]]
Router = Callable[[dict[str, Any]], str]
Reducer = Callable[[Any, Any], Any]


class GraphError(Exception):
    pass


class StateGraph:
    """Nodes, edges and a shared state dict. That is the whole model.

    __init__(self, reducers: dict[str, Reducer] | None = None)
      self.nodes: dict[str, Node]
      self.edges: dict[str, str]                                  unconditional
      self.conditional: dict[str, tuple[Router, dict[str, str]]]  branching
      self.entry: str | None
    """

    def __init__(self, reducers: dict[str, Reducer] | None = None) -> None:
        # TODO: implement
        raise NotImplementedError

    def add_node(self, name: str, node: Node) -> "StateGraph":
        """Raise GraphError for a reserved name (START/END) or a duplicate.
        Return self to chain."""
        # TODO: implement
        raise NotImplementedError

    def add_edge(self, source: str, target: str) -> "StateGraph":
        """An unconditional edge. Raise if `source` already has conditional edges
        — a node with both is ambiguous, and silently preferring one is worse than
        refusing."""
        # TODO: implement
        raise NotImplementedError

    def add_conditional_edges(self, source: str, router: Router,
                              mapping: dict[str, str]) -> "StateGraph":
        """Branch on a router's return value. Raise if `source` already has an
        unconditional edge.

        The router returns a KEY and the mapping turns it into a node name. That
        indirection looks redundant until you rewire a graph without touching the
        routing logic — which is exactly what adding a step involves.
        """
        # TODO: implement
        raise NotImplementedError

    def set_entry(self, name: str) -> "StateGraph":
        # TODO: implement
        raise NotImplementedError

    def validate(self) -> None:
        """Catch, at build time, the mistakes that would otherwise be runtime hangs.

        Raise GraphError for:
          * no entry set                              "no entry point; call set_entry()"
          * entry is not a node
          * an edge FROM an unknown node
          * an edge TO an unknown node (END is fine)
          * a conditional edge from an unknown node
          * a conditional target that is unknown (END is fine)
          * A NODE WITH NO OUTGOING EDGE — this is the important one. At runtime it
            is a KeyError three steps into the run, or a silent stall. Here it is a
            sentence naming the node.

        This method IS the argument for using a graph framework. Everything else
        you can do with a while loop.
        """
        # TODO: implement
        raise NotImplementedError

    def compile(self) -> "Any":
        """validate(), then return a CompiledGraph (Exercise 3)."""
        # TODO: implement
        raise NotImplementedError

    def to_mermaid(self) -> str:
        """A Mermaid diagram.

            graph TD
                __start__([start]) --> think
                think -->|act| act
                think -->|done| __end__
                act --> think

        Being able to SEE the graph is honestly most of the appeal of a graph
        framework, so it is worth ten lines.
        """
        # TODO: implement
        raise NotImplementedError
