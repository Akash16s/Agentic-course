"""Tests for Chapter 10, Exercise 1 — datasets."""

import json

import pytest

from chapters.ch10_evals_basics.exercises.exercise_1_dataset import Dataset, EvalCase


class TestEvalCase:
    def test_defaults(self):
        c = EvalCase(id="1", input="q")
        assert c.expected is None
        assert c.tags == []
        assert c.metadata == {}

    def test_defaults_are_not_shared(self):
        a, b = EvalCase(id="1", input="q"), EvalCase(id="2", input="q")
        a.tags.append("x")
        assert b.tags == []


class TestDataset:
    def test_empty(self):
        d = Dataset()
        assert len(d) == 0
        assert list(d) == []

    def test_from_cases(self):
        d = Dataset([EvalCase(id="1", input="a"), EvalCase(id="2", input="b")])
        assert len(d) == 2

    def test_iterable(self):
        d = Dataset([EvalCase(id="1", input="a")])
        assert [c.id for c in d] == ["1"]

    def test_name(self):
        assert Dataset(name="support-v3").name == "support-v3"


class TestFilter:
    def cases(self):
        return [
            EvalCase(id="1", input="a", tags=["math"]),
            EvalCase(id="2", input="b", tags=["negative"]),
            EvalCase(id="3", input="c", tags=["math", "hard"]),
        ]

    def test_by_tag(self):
        d = Dataset(self.cases()).filter(tag="math")
        assert [c.id for c in d] == ["1", "3"]

    def test_by_predicate(self):
        d = Dataset(self.cases()).filter(predicate=lambda c: c.input == "b")
        assert [c.id for c in d] == ["2"]

    def test_both(self):
        d = Dataset(self.cases()).filter(tag="math", predicate=lambda c: "hard" in c.tags)
        assert [c.id for c in d] == ["3"]

    def test_returns_a_new_dataset(self):
        original = Dataset(self.cases())
        filtered = original.filter(tag="math")
        assert filtered is not original
        assert len(original) == 3

    def test_no_matches(self):
        assert len(Dataset(self.cases()).filter(tag="nope")) == 0


class TestJsonl:
    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "d.jsonl")
        original = Dataset([
            EvalCase(id="1", input="q1", expected="a1", tags=["x"], metadata={"k": 1}),
            EvalCase(id="2", input="q2", expected=["a", "b"]),
        ])
        original.to_jsonl(path)
        loaded = Dataset.from_jsonl(path)
        assert len(loaded) == 2
        assert loaded.cases[0].expected == "a1"
        assert loaded.cases[0].tags == ["x"]
        assert loaded.cases[0].metadata == {"k": 1}
        assert loaded.cases[1].expected == ["a", "b"]

    def test_one_object_per_line(self, tmp_path):
        path = str(tmp_path / "d.jsonl")
        Dataset([EvalCase(id=str(i), input=f"q{i}") for i in range(3)]).to_jsonl(path)
        with open(path) as handle:
            lines = [l for l in handle if l.strip()]
        assert len(lines) == 3
        for line in lines:
            json.loads(line)

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "d.jsonl"
        path.write_text('{"input": "a"}\n\n\n{"input": "b"}\n')
        assert len(Dataset.from_jsonl(str(path))) == 2

    def test_skips_comments(self, tmp_path):
        # people comment their eval files; a loader that crashes is worked around
        path = tmp_path / "d.jsonl"
        path.write_text('// the easy ones\n{"input": "a"}\n// the hard ones\n{"input": "b"}\n')
        assert len(Dataset.from_jsonl(str(path))) == 2

    def test_id_defaults_to_the_line_number(self, tmp_path):
        path = tmp_path / "d.jsonl"
        path.write_text('{"input": "a"}\n{"input": "b"}\n')
        assert [c.id for c in Dataset.from_jsonl(str(path))] == ["1", "2"]

    def test_missing_input_is_an_error(self, tmp_path):
        # a case with no input is a broken file, not something to tolerate
        path = tmp_path / "d.jsonl"
        path.write_text('{"expected": "a"}\n')
        with pytest.raises(KeyError):
            Dataset.from_jsonl(str(path))

    def test_name_defaults_to_the_path(self, tmp_path):
        path = tmp_path / "d.jsonl"
        path.write_text('{"input": "a"}\n')
        assert Dataset.from_jsonl(str(path)).name == str(path)

    def test_explicit_name(self, tmp_path):
        path = tmp_path / "d.jsonl"
        path.write_text('{"input": "a"}\n')
        assert Dataset.from_jsonl(str(path), name="mine").name == "mine"
