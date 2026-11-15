"""Tests for Chapter 17, Exercise 3 — running the graph."""

import pytest

from chapters.ch17_frameworks.exercises.exercise_1_reducers import END, add, append
from chapters.ch17_frameworks.exercises.exercise_2_graph import GraphError, StateGraph
from chapters.ch17_frameworks.exercises.exercise_3_execution import (
    CompiledGraph,
    GraphResult,
    Step,
)


def linear():
    g = StateGraph({"trail": append})
    g.add_node("a", lambda s: {"trail": "a"})
    g.add_node("b", lambda s: {"trail": "b"})
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    return g.compile()


def looping(limit=3):
    g = StateGraph({"trail": append, "n": add})
    g.add_node("step", lambda s: {"trail": f"step{s['n']}", "n": 1})
    g.set_entry("step")
    g.add_conditional_edges("step", lambda s: "done" if s["n"] >= limit else "again",
                            {"again": "step", "done": END})
    return g.compile()


class TestLinear:
    def test_runs_both_nodes(self):
        result = linear().invoke({"trail": []})
        assert result.path == ["a", "b"]

    def test_accumulates_state(self):
        assert linear().invoke({"trail": []}).state["trail"] == ["a", "b"]

    def test_records_updates(self):
        steps = linear().invoke({"trail": []}).steps
        assert steps[0].update == {"trail": "a"}

    def test_step_snapshots_are_after_merging(self):
        steps = linear().invoke({"trail": []}).steps
        assert steps[0].state["trail"] == ["a"]
        assert steps[1].state["trail"] == ["a", "b"]

    def test_snapshots_are_independent(self):
        steps = linear().invoke({"trail": []}).steps
        steps[0].state["trail"].append("tampered")
        assert steps[1].state["trail"] == ["a", "b"]

    def test_does_not_mutate_the_caller_state(self):
        initial = {"trail": []}
        linear().invoke(initial)
        assert initial == {"trail": []}


class TestLooping:
    def test_cycles_until_the_router_says_done(self):
        result = looping(3).invoke({"trail": [], "n": 0})
        assert result.path == ["step", "step", "step"]
        assert result.state["n"] == 3

    def test_reducers_apply_per_key(self):
        result = looping(3).invoke({"trail": [], "n": 0})
        assert result.state["trail"] == ["step0", "step1", "step2"]

    def test_stops_at_max_steps(self):
        # a graph with a cycle is the same infinite loop wearing a diagram
        g = StateGraph()
        g.add_node("spin", lambda s: {})
        g.set_entry("spin")
        g.add_edge("spin", "spin")
        result = g.compile().invoke({}, max_steps=7)
        assert len(result.steps) == 7
        assert result.stopped_early

    def test_a_completed_run_is_not_stopped_early(self):
        assert not looping(3).invoke({"trail": [], "n": 0}).stopped_early


class TestStream:
    def test_yields_incrementally(self):
        seen = []
        for step in looping(3).stream({"trail": [], "n": 0}):
            seen.append(step.node)
        assert seen == ["step"] * 3

    def test_a_step_is_available_before_the_run_finishes(self):
        stream = looping(5).stream({"trail": [], "n": 0})
        first = next(stream)
        assert first.state["n"] == 1

    def test_stream_respects_max_steps(self):
        g = StateGraph()
        g.add_node("spin", lambda s: {})
        g.set_entry("spin").add_edge("spin", "spin")
        assert len(list(g.compile().stream({}, max_steps=4))) == 4


class TestMerging:
    def test_unlisted_keys_are_replaced(self):
        g = StateGraph({"trail": append})
        g.add_node("a", lambda s: {"trail": "a", "answer": "first"})
        g.add_node("b", lambda s: {"trail": "b", "answer": "second"})
        g.set_entry("a").add_edge("a", "b").add_edge("b", END)
        result = g.compile().invoke({"trail": []})
        assert result.state["answer"] == "second"
        assert result.state["trail"] == ["a", "b"]

    def test_a_node_returning_none_changes_nothing(self):
        g = StateGraph({"trail": append})
        g.add_node("a", lambda s: None)
        g.set_entry("a").add_edge("a", END)
        assert g.compile().invoke({"trail": ["x"]}).state["trail"] == ["x"]

    def test_untouched_keys_survive(self):
        g = StateGraph()
        g.add_node("a", lambda s: {"x": 1})
        g.set_entry("a").add_edge("a", END)
        assert g.compile().invoke({"keep": "me"}).state["keep"] == "me"

    def test_nodes_can_read_the_state(self):
        g = StateGraph()
        g.add_node("a", lambda s: {"doubled": s["n"] * 2})
        g.set_entry("a").add_edge("a", END)
        assert g.compile().invoke({"n": 21}).state["doubled"] == 42


class TestRouting:
    def test_branches(self):
        g = StateGraph()
        g.add_node("start", lambda s: {})
        g.add_node("left", lambda s: {"went": "left"})
        g.add_node("right", lambda s: {"went": "right"})
        g.set_entry("start")
        g.add_conditional_edges("start", lambda s: s["pick"],
                                {"l": "left", "r": "right"})
        g.add_edge("left", END)
        g.add_edge("right", END)
        compiled = g.compile()
        assert compiled.invoke({"pick": "l"}).state["went"] == "left"
        assert compiled.invoke({"pick": "r"}).state["went"] == "right"

    def test_an_unmapped_router_key_raises_clearly(self):
        # silently falling through would stall the graph with no useful message
        g = StateGraph()
        g.add_node("a", lambda s: {})
        g.set_entry("a")
        g.add_conditional_edges("a", lambda s: "surprise", {"x": END})
        with pytest.raises(GraphError) as exc:
            g.compile().invoke({})
        assert "surprise" in str(exc.value)

    def test_the_router_sees_the_merged_state(self):
        g = StateGraph({"n": add})
        g.add_node("a", lambda s: {"n": 1})
        g.set_entry("a")
        g.add_conditional_edges("a", lambda s: "done" if s["n"] == 1 else "again",
                                {"again": "a", "done": END})
        assert len(g.compile().invoke({"n": 0}).steps) == 1


class TestResult:
    def test_empty_graph_run(self):
        g = StateGraph()
        g.add_node("a", lambda s: {})
        g.set_entry("a").add_edge("a", END)
        result = g.compile().invoke({"x": 1})
        assert result.state["x"] == 1

    def test_path(self):
        assert linear().invoke({"trail": []}).path == ["a", "b"]
