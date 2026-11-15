"""Tests for Chapter 17, Exercise 2 — building and validating."""

import pytest

from chapters.ch17_frameworks.exercises.exercise_1_reducers import END, START, append
from chapters.ch17_frameworks.exercises.exercise_2_graph import GraphError, StateGraph


def noop(state):
    return {}


class TestBuilding:
    def test_add_node(self):
        g = StateGraph()
        g.add_node("a", noop)
        assert "a" in g.nodes

    def test_chaining(self):
        g = StateGraph()
        assert g.add_node("a", noop) is g

    def test_duplicate_node(self):
        g = StateGraph().add_node("a", noop)
        with pytest.raises(GraphError):
            g.add_node("a", noop)

    @pytest.mark.parametrize("name", [START, END])
    def test_reserved_names(self, name):
        with pytest.raises(GraphError):
            StateGraph().add_node(name, noop)

    def test_edges(self):
        g = StateGraph().add_node("a", noop).add_node("b", noop)
        g.add_edge("a", "b")
        assert g.edges["a"] == "b"

    def test_conditional_edges(self):
        g = StateGraph().add_node("a", noop).add_node("b", noop)
        g.add_conditional_edges("a", lambda s: "go", {"go": "b"})
        assert "a" in g.conditional

    def test_cannot_mix_edge_types(self):
        # a node with both is ambiguous; silently preferring one is worse
        g = StateGraph().add_node("a", noop).add_node("b", noop)
        g.add_edge("a", "b")
        with pytest.raises(GraphError):
            g.add_conditional_edges("a", lambda s: "x", {"x": "b"})

    def test_cannot_mix_the_other_way(self):
        g = StateGraph().add_node("a", noop).add_node("b", noop)
        g.add_conditional_edges("a", lambda s: "x", {"x": "b"})
        with pytest.raises(GraphError):
            g.add_edge("a", "b")

    def test_reducers_are_stored(self):
        assert StateGraph({"messages": append}).reducers["messages"] is append


class TestValidation:
    def linear(self):
        g = StateGraph()
        g.add_node("a", noop).add_node("b", noop)
        g.set_entry("a")
        g.add_edge("a", "b")
        g.add_edge("b", END)
        return g

    def test_a_valid_graph_compiles(self):
        self.linear().compile()

    def test_no_entry(self):
        g = StateGraph().add_node("a", noop).add_edge("a", END)
        with pytest.raises(GraphError, match="entry"):
            g.validate()

    def test_entry_is_not_a_node(self):
        g = StateGraph().add_node("a", noop).add_edge("a", END)
        g.set_entry("ghost")
        with pytest.raises(GraphError):
            g.validate()

    def test_edge_from_an_unknown_node(self):
        g = self.linear()
        g.edges["ghost"] = "a"
        with pytest.raises(GraphError):
            g.validate()

    def test_edge_to_an_unknown_node(self):
        g = StateGraph().add_node("a", noop).set_entry("a").add_edge("a", "ghost")
        with pytest.raises(GraphError, match="ghost"):
            g.validate()

    def test_end_is_a_valid_target(self):
        StateGraph().add_node("a", noop).set_entry("a").add_edge("a", END).validate()

    def test_a_node_with_no_outgoing_edge(self):
        # at runtime this is a KeyError three steps later, or a silent stall
        g = StateGraph().add_node("a", noop).add_node("orphan", noop)
        g.set_entry("a").add_edge("a", END)
        with pytest.raises(GraphError, match="orphan"):
            g.validate()

    def test_conditional_target_must_exist(self):
        g = StateGraph().add_node("a", noop).set_entry("a")
        g.add_conditional_edges("a", lambda s: "x", {"x": "ghost"})
        with pytest.raises(GraphError, match="ghost"):
            g.validate()

    def test_error_messages_name_the_node(self):
        g = StateGraph().add_node("summarise", noop).add_node("a", noop)
        g.set_entry("a").add_edge("a", END)
        with pytest.raises(GraphError) as exc:
            g.validate()
        assert "summarise" in str(exc.value)

    def test_compile_validates(self):
        with pytest.raises(GraphError):
            StateGraph().compile()


class TestMermaid:
    def test_includes_the_nodes(self):
        g = StateGraph().add_node("a", noop).add_node("b", noop)
        g.set_entry("a").add_edge("a", "b").add_edge("b", END)
        out = g.to_mermaid()
        assert "a --> b" in out
        assert out.startswith("graph TD")

    def test_shows_the_entry(self):
        g = StateGraph().add_node("a", noop).set_entry("a").add_edge("a", END)
        assert START in g.to_mermaid()

    def test_labels_conditional_edges(self):
        g = StateGraph().add_node("a", noop).add_node("b", noop)
        g.set_entry("a")
        g.add_conditional_edges("a", lambda s: "go", {"go": "b", "stop": END})
        g.add_edge("b", END)
        out = g.to_mermaid()
        assert "|go|" in out and "|stop|" in out
