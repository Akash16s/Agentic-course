"""Tests for Chapter 11, Exercise 1 — the judge."""

import pytest

from agentlib.evals.core import EvalCase
from chapters.ch11_evals_judges.exercises.exercise_1_judge import Judgement, LLMJudge

RUBRIC = "5 = perfect\n3 = acceptable\n1 = wrong"


def judge(response_text, **kwargs):
    return LLMJudge(RUBRIC, lambda prompt: response_text, **kwargs)


class TestConstruction:
    def test_empty_rubric_raises(self):
        # a judge without a rubric still confidently produces numbers
        with pytest.raises(ValueError):
            LLMJudge("", lambda p: "")
        with pytest.raises(ValueError):
            LLMJudge("   ", lambda p: "")

    def test_default_pass_threshold(self):
        # 80% of the way up a 1-5 scale
        assert judge("").pass_at == pytest.approx(4.2)

    def test_custom_scale(self):
        j = judge("", scale=(0, 10))
        assert j.low == 0 and j.high == 10
        assert j.pass_at == pytest.approx(8.0)

    def test_explicit_pass_at(self):
        assert judge("", pass_at=3.0).pass_at == 3.0


class TestPrompt:
    def test_includes_the_pieces(self):
        prompt = judge("").prompt("summarise X", "X is a thing")
        assert "summarise X" in prompt
        assert "X is a thing" in prompt
        assert "5 = perfect" in prompt

    def test_includes_the_scale(self):
        assert "1-5" in judge("").prompt("t", "r")

    def test_reference_is_optional(self):
        assert "REFERENCE" not in judge("").prompt("t", "r")

    def test_reference_is_included_when_given(self):
        prompt = judge("").prompt("t", "r", "the known-good answer")
        assert "the known-good answer" in prompt

    def test_reasoning_is_requested_before_score(self):
        # chain-of-thought; swapping them measurably degrades consistency
        prompt = judge("").prompt("t", "r")
        assert prompt.index("reasoning") < prompt.index('"score"')


class TestParse:
    def test_clean_judgement(self):
        j = judge("")
        result = j.parse('{"reasoning": "all good", "score": 5, "passed": true}')
        assert result.score == 5.0
        assert result.passed
        assert result.reasoning == "all good"

    def test_fenced(self):
        result = judge("").parse('```json\n{"score": 4, "passed": false}\n```')
        assert result.score == 4.0

    def test_passed_is_derived_when_absent(self):
        assert judge("").parse('{"score": 5}').passed
        assert not judge("").parse('{"score": 2}').passed

    def test_score_is_clamped_to_the_scale(self):
        assert judge("").parse('{"score": 99}').score == 5.0
        assert judge("").parse('{"score": -3}').score == 1.0

    def test_non_numeric_score_falls_to_the_minimum(self):
        assert judge("").parse('{"score": "great"}').score == 1.0

    def test_bare_number_in_prose(self):
        result = judge("").parse("I would give this a 4 out of 5.")
        assert result.score == 4.0
        assert "unstructured" in result.reasoning

    def test_fails_closed_on_garbage(self):
        # a judge that fails OPEN silently inflates your scores for months
        result = judge("").parse("I'm not able to grade that.")
        assert result.score == 1.0
        assert not result.passed

    def test_fails_closed_on_empty(self):
        assert not judge("").parse("").passed
        assert judge("").parse("").score == 1.0

    def test_keeps_the_raw_output(self):
        assert judge("").parse("weird output").raw == "weird output"

    def test_never_raises(self):
        for raw in ["", "{", "null", "[]", '{"score": null}', "{}"]:
            judge("").parse(raw)


class TestGrade:
    def test_end_to_end(self):
        seen = []

        def call(prompt):
            seen.append(prompt)
            return '{"score": 5, "passed": true, "reasoning": "fine"}'

        result = LLMJudge(RUBRIC, call).grade("the task", "the response")
        assert result.score == 5.0
        assert "the task" in seen[0]


class TestAsCheck:
    def test_passing(self):
        check = judge('{"score": 5, "passed": true, "reasoning": "good"}').as_check()
        result = check("some output", EvalCase(id="1", input="q"))
        assert result.passed
        assert result.name == "judge"
        assert result.score == 5.0

    def test_failing_includes_the_reasoning(self):
        check = judge('{"score": 2, "passed": false, "reasoning": "made things up"}').as_check()
        result = check("bad output", EvalCase(id="1", input="q"))
        assert not result.passed
        assert "made things up" in result.detail

    def test_score_is_recorded_even_on_a_pass(self):
        check = judge('{"score": 5, "passed": true}').as_check()
        assert check("x", EvalCase(id="1", input="q")).score == 5.0

    def test_uses_the_expected_value_as_a_reference(self):
        seen = []

        def call(prompt):
            seen.append(prompt)
            return '{"score": 5, "passed": true}'

        check = LLMJudge(RUBRIC, call).as_check()
        check("out", EvalCase(id="1", input="q", expected="the gold answer"))
        assert "the gold answer" in seen[0]

    def test_reference_can_be_disabled(self):
        seen = []

        def call(prompt):
            seen.append(prompt)
            return '{"score": 5, "passed": true}'

        check = LLMJudge(RUBRIC, call).as_check(reference_from_case=False)
        check("out", EvalCase(id="1", input="q", expected="the gold answer"))
        assert "the gold answer" not in seen[0]

    def test_custom_name(self):
        check = judge('{"score": 5}').as_check(name="helpfulness")
        assert check("x", EvalCase(id="1", input="q")).name == "helpfulness"

    def test_works_with_an_agent_result(self):
        class Result:
            output = "the agent's answer"

        check = judge('{"score": 5, "passed": true}').as_check()
        assert check(Result(), EvalCase(id="1", input="q")).passed
