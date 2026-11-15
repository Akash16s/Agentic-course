"""Tests for Chapter 11, Exercise 2 — pairwise comparison."""

import pytest

from chapters.ch11_evals_judges.exercises.exercise_2_pairwise import (
    ask_pairwise,
    json_object,
    pairwise_compare,
)

RUBRIC = "prefer the more accurate answer"


def scripted(*answers):
    it = iter(answers)
    return lambda prompt: next(it)


class TestAskPairwise:
    def test_a(self):
        assert ask_pairwise("t", "x", "y", RUBRIC, scripted('{"winner": "A"}'))[0] == "a"

    def test_b(self):
        assert ask_pairwise("t", "x", "y", RUBRIC, scripted('{"winner": "B"}'))[0] == "b"

    def test_tie(self):
        assert ask_pairwise("t", "x", "y", RUBRIC, scripted('{"winner": "tie"}'))[0] == "tie"

    def test_lowercase(self):
        assert ask_pairwise("t", "x", "y", RUBRIC, scripted('{"winner": "a"}'))[0] == "a"

    def test_garbage_becomes_a_tie(self):
        # a judge that produced garbage has not expressed a preference
        assert ask_pairwise("t", "x", "y", RUBRIC, scripted("no idea"))[0] == "tie"

    def test_unknown_winner_becomes_a_tie(self):
        assert ask_pairwise("t", "x", "y", RUBRIC,
                            scripted('{"winner": "C"}'))[0] == "tie"

    def test_returns_the_reasoning(self):
        _, reasoning = ask_pairwise(
            "t", "x", "y", RUBRIC, scripted('{"winner":"A","reasoning":"more precise"}')
        )
        assert reasoning == "more precise"

    def test_prompt_contains_both_answers(self):
        seen = []
        ask_pairwise("t", "first answer", "second answer", RUBRIC,
                     lambda p: seen.append(p) or '{"winner":"A"}')
        assert "first answer" in seen[0] and "second answer" in seen[0]


class TestPositionBias:
    def test_a_judge_that_always_says_first_is_a_tie(self):
        # this is what pure position bias looks like, and it MUST NOT read as a win
        result = pairwise_compare("t", "x", "y", RUBRIC,
                                  scripted('{"winner":"A"}', '{"winner":"A"}'))
        assert result.winner == "tie"
        assert result.swapped_agreement is False

    def test_a_judge_that_always_says_second_is_also_a_tie(self):
        result = pairwise_compare("t", "x", "y", RUBRIC,
                                  scripted('{"winner":"B"}', '{"winner":"B"}'))
        assert result.winner == "tie"

    def test_genuine_preference_for_a(self):
        # picks A first time, B second time -> both times it chose answer_a
        result = pairwise_compare("t", "x", "y", RUBRIC,
                                  scripted('{"winner":"A"}', '{"winner":"B"}'))
        assert result.winner == "a"
        assert result.swapped_agreement is True

    def test_genuine_preference_for_b(self):
        result = pairwise_compare("t", "x", "y", RUBRIC,
                                  scripted('{"winner":"B"}', '{"winner":"A"}'))
        assert result.winner == "b"
        assert result.swapped_agreement is True

    def test_consistent_tie(self):
        result = pairwise_compare("t", "x", "y", RUBRIC,
                                  scripted('{"winner":"tie"}', '{"winner":"tie"}'))
        assert result.winner == "tie"
        assert result.swapped_agreement is True

    def test_two_calls_are_made(self):
        calls = []
        pairwise_compare("t", "x", "y", RUBRIC,
                         lambda p: calls.append(p) or '{"winner":"A"}')
        assert len(calls) == 2

    def test_the_second_call_swaps_the_answers(self):
        calls = []
        pairwise_compare("t", "FIRST", "SECOND", RUBRIC,
                         lambda p: calls.append(p) or '{"winner":"A"}')
        first_a = calls[0].split("ANSWER A:")[1].split("ANSWER B:")[0]
        second_a = calls[1].split("ANSWER A:")[1].split("ANSWER B:")[0]
        assert "FIRST" in first_a
        assert "SECOND" in second_a

    def test_disagreement_is_explained(self):
        result = pairwise_compare("t", "x", "y", RUBRIC,
                                  scripted('{"winner":"A"}', '{"winner":"A"}'))
        assert "order" in result.reasoning.lower()


class TestWithoutControl:
    def test_only_one_call(self):
        calls = []
        pairwise_compare("t", "x", "y", RUBRIC,
                         lambda p: calls.append(p) or '{"winner":"A"}',
                         control_position_bias=False)
        assert len(calls) == 1

    def test_reports_the_biased_answer_as_a_win(self):
        # what you get without the control: the judge's layout preference
        result = pairwise_compare("t", "x", "y", RUBRIC, scripted('{"winner":"A"}'),
                                  control_position_bias=False)
        assert result.winner == "a"
        assert result.swapped_agreement is None


class TestJsonObject:
    def test_plain(self):
        assert json_object('{"a": 1}') == {"a": 1}

    def test_prose(self):
        assert json_object('sure: {"a": 1}') == {"a": 1}

    def test_none_on_failure(self):
        assert json_object("no json") is None
