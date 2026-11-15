"""Tests for Chapter 7, Exercise 4 — reflection."""

import pytest

from chapters.ch07_planning.exercises.exercise_4_reflection import (
    Critique,
    json_object,
    parse_critique,
    reflect_loop,
)


class TestJsonObject:
    def test_plain(self):
        assert json_object('{"a": 1}') == {"a": 1}

    def test_prose_around_it(self):
        assert json_object('Sure: {"a": 1} done') == {"a": 1}

    def test_fence(self):
        assert json_object('```json\n{"a": 1}\n```') == {"a": 1}

    def test_malformed(self):
        assert json_object('{"a":') is None

    def test_empty(self):
        assert json_object("") is None

    def test_an_array_is_not_an_object(self):
        assert json_object("[1,2]") is None


class TestParseCritique:
    def test_rejection(self):
        c = parse_critique('{"acceptable": false, "issues": ["no citation"], '
                           '"suggestion": "cite the source"}')
        assert not c.acceptable
        assert c.issues == ["no citation"]
        assert c.suggestion == "cite the source"

    def test_acceptance(self):
        c = parse_critique('{"acceptable": true, "issues": []}')
        assert c.acceptable

    def test_issues_override_a_claimed_acceptance(self):
        # a critic that says "fine" then lists three problems has contradicted
        # itself; believe the problems
        c = parse_critique('{"acceptable": true, "issues": ["missing X"]}')
        assert not c.acceptable

    def test_issues_without_the_flag_means_rejection(self):
        assert not parse_critique('{"issues": ["bad"]}').acceptable

    def test_no_issues_without_the_flag_means_acceptance(self):
        assert parse_critique('{"issues": []}').acceptable

    def test_blank_issues_are_dropped(self):
        c = parse_critique('{"acceptable": false, "issues": ["", "  ", "real"]}')
        assert c.issues == ["real"]

    def test_fails_open_on_unparseable_output(self):
        # failing closed turns one malformed response into an endless revision loop
        assert parse_critique("I think it's fine, honestly").acceptable
        assert parse_critique("").acceptable
        assert parse_critique("{{{").acceptable

    def test_summary(self):
        assert parse_critique('{"acceptable": true}').summary == "acceptable"
        assert "a; b" in parse_critique('{"issues": ["a","b"]}').summary

    def test_summary_with_no_issues_but_rejected(self):
        c = Critique(acceptable=False)
        assert c.summary == "unspecified problems"


class TestReflectLoop:
    def test_accepted_first_time(self):
        produced = []

        def produce(feedback):
            produced.append(feedback)
            return "an answer"

        answer, critiques = reflect_loop(
            "task", produce, lambda t, a: Critique(acceptable=True)
        )
        assert answer == "an answer"
        assert produced == [None], "no revision when the first answer is accepted"
        assert len(critiques) == 1

    def test_revises_once(self):
        produced = []
        seen = iter([Critique(False, ["wrong"], "fix it"), Critique(True)])

        def produce(feedback):
            produced.append(feedback)
            return f"answer for {feedback}"

        answer, critiques = reflect_loop("task", produce, lambda t, a: next(seen))
        assert produced == [None, "fix it"]
        assert answer == "answer for fix it"
        assert len(critiques) == 2

    def test_stops_at_max_rounds(self):
        calls = []

        def produce(feedback):
            calls.append(feedback)
            return "still wrong"

        answer, critiques = reflect_loop(
            "task", produce,
            lambda t, a: Critique(False, ["nope"], "try again"),
            max_rounds=2,
        )
        assert len(critiques) == 2
        assert len(calls) == 3  # initial + 2 revisions

    def test_falls_back_to_the_summary_when_there_is_no_suggestion(self):
        seen = iter([Critique(False, ["missing X"]), Critique(True)])
        got = []
        reflect_loop("task", lambda f: got.append(f) or "a", lambda t, a: next(seen))
        assert got[1] == "missing X"

    def test_critic_sees_the_current_answer(self):
        seen = []

        def criticise(task, answer):
            seen.append(answer)
            return Critique(acceptable=len(seen) > 1)

        reflect_loop("task", lambda f: f"v{len(seen)}", criticise)
        assert seen[0] != seen[1]

    def test_max_rounds_zero_produces_without_critiquing(self):
        answer, critiques = reflect_loop(
            "t", lambda f: "a", lambda t, a: Critique(False), max_rounds=0
        )
        assert answer == "a"
        assert critiques == []
