"""Tests for Chapter 13b, Exercise 3 — heuristic and LLM routers."""

import pytest

from agentlib import errors
from agentlib.llm import LLMResponse, Usage
from agentlib.testing import FakeLLMClient
from chapters.ch13b_routing.exercises.exercise_3_router import (
    EASY,
    HARD,
    HeuristicRouter,
    LLMRouter,
    RouteDecision,
    RoutedClient,
    last_user_text,
    parse_label,
)

CODE = "```python\nprint('hi')\n```"


class TestFeatures:
    def test_the_four_keys(self):
        f = HeuristicRouter().features("hello")
        assert set(f) == {"length", "code_blocks", "keywords", "questions"}

    def test_code_blocks_count_pairs_of_fences(self):
        assert HeuristicRouter().features(CODE)["code_blocks"] == 1
        assert HeuristicRouter().features(CODE + "\n" + CODE)["code_blocks"] == 2
        assert HeuristicRouter().features("no code")["code_blocks"] == 0

    def test_keywords_are_case_insensitive_and_in_list_order(self):
        f = HeuristicRouter().features("Please REFACTOR this, then Prove it works")
        assert f["keywords"] == ["prove", "refactor"]

    def test_multi_word_keyword(self):
        assert HeuristicRouter().features("think step by step")["keywords"] == [
            "step by step"]

class TestHeuristicRoute:
    def test_plain_short_question_is_easy(self):
        d = HeuristicRouter().route("What is the capital of France?")
        assert isinstance(d, RouteDecision)
        assert d.tier == EASY
        assert d.score == 0.0
        assert d.reasons == []

    def test_long_input_scores_one(self):
        d = HeuristicRouter(long_chars=100).route("x" * 100)
        assert d.score == pytest.approx(1.0)
        assert d.tier == EASY

    def test_code_plus_keyword_is_hard(self):
        d = HeuristicRouter().route("Refactor this:\n" + CODE)
        assert d.score == pytest.approx(2.0)
        assert d.tier == HARD

    def test_keywords_are_capped_at_two(self):
        text = "prove, derive, debug, refactor and optimise this"
        assert HeuristicRouter().route(text).score == pytest.approx(2.0)

    def test_questions_beyond_the_first_count_half(self):
        assert HeuristicRouter().route("a? b?").score == pytest.approx(0.5)

    def test_questions_are_capped_at_one(self):
        assert HeuristicRouter().route("?" * 10).score == pytest.approx(1.0)

    def test_threshold_is_respected(self):
        text = "Please debug this"
        assert HeuristicRouter(threshold=2.0).route(text).tier == EASY
        assert HeuristicRouter(threshold=1.0).route(text).tier == HARD

    def test_reasons_explain_the_score(self):
        d = HeuristicRouter(long_chars=50).route("debug " + "x" * 50 + "\n" + CODE)
        joined = " ".join(d.reasons)
        assert "keyword: debug" in d.reasons
        assert "long" in joined
        assert "code" in joined

    def test_custom_keywords(self):
        router = HeuristicRouter(keywords=("legal",), threshold=1.0)
        assert router.route("a legal question").tier == HARD
        assert router.route("please refactor").tier == EASY


class TestParseLabel:
    @pytest.mark.parametrize("reply,expected", [
        ("easy", EASY),
        ("HARD.", HARD),
        ("**easy**", EASY),
        ("The task is hard", HARD),
    ])
    def test_finds_the_label(self, reply, expected):
        assert parse_label(reply) == expected

    @pytest.mark.parametrize("reply", [
        "easy or hard",          # hedged
        "medium",
        "hardly anything",       # a substring is not a word
        "uneasy",
    ])
    def test_returns_none_when_unclear(self, reply):
        assert parse_label(reply) is None


class TestLLMRouter:
    def test_easy_reply_routes_easy(self):
        d = LLMRouter(FakeLLMClient(["easy"])).route("2+2?")
        assert d.tier == EASY
        assert d.score == 0.0

    def test_hard_reply_routes_hard(self):
        d = LLMRouter(FakeLLMClient(["hard"])).route("prove P != NP")
        assert d.tier == HARD
        assert d.score == 1.0

    def test_sends_the_task_inside_the_prompt(self):
        fake = FakeLLMClient(["easy"])
        LLMRouter(fake).route("what is 2+2")
        sent = fake.last_messages
        assert len(sent) == 1 and sent[0]["role"] == "user"
        assert "what is 2+2" in sent[0]["content"]

    def test_asks_deterministically_and_briefly(self):
        fake = FakeLLMClient(["easy"])
        LLMRouter(fake).route("x")
        kwargs = fake.calls[0][1]
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] <= 10

    def test_truncates_long_input(self):
        fake = FakeLLMClient(["hard"])
        LLMRouter(fake, max_chars=100).route("Z" * 5_000)
        assert fake.last_messages[0]["content"].count("Z") == 100

    def test_unparseable_reply_uses_the_safe_default(self):
        d = LLMRouter(FakeLLMClient(["I think it is medium"])).route("x")
        assert d.tier == HARD
        assert "unparseable" in " ".join(d.reasons)

    def test_invalid_default_is_rejected(self):
        with pytest.raises(ValueError):
            LLMRouter(FakeLLMClient(), default="medium")

    def test_router_outage_does_not_raise(self):
        d = LLMRouter(FakeLLMClient([errors.ServerError("down")])).route("x")
        assert d.tier == HARD
        assert "error" in " ".join(d.reasons)

    def test_tracks_its_own_cost(self):
        fake = FakeLLMClient([LLMResponse("easy", usage=Usage(120, 1)),
                              LLMResponse("hard", usage=Usage(80, 1))])
        router = LLMRouter(fake)
        router.route("a")
        router.route("b")
        assert router.calls == 2
        assert router.total_usage == Usage(200, 2)


class TestLastUserText:
    def test_picks_the_last_user_message(self):
        msgs = [{"role": "system", "content": "sys"},
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply"},
                {"role": "user", "content": "second"}]
        assert last_user_text(msgs) == "second"

    def test_non_string_content(self):
        msgs = [{"role": "user", "content": [{"type": "image_url"}]}]
        assert last_user_text(msgs) == ""


class TestRoutedClient:
    def test_sends_hard_requests_to_the_hard_client(self):
        easy, hard = FakeLLMClient(["cheap"]), FakeLLMClient(["strong"])
        client = RoutedClient(HeuristicRouter(threshold=1.0),
                              {EASY: easy, HARD: hard})
        r = client.chat([{"role": "user", "content": "debug this"}])
        assert r.text == "strong"
        assert easy.call_count == 0

    def test_forwards_messages_and_kwargs(self):
        easy = FakeLLMClient(["ok"])
        client = RoutedClient(HeuristicRouter(), {EASY: easy, HARD: FakeLLMClient()})
        msgs = [{"role": "user", "content": "hi"}]
        client.chat(msgs, max_tokens=20)
        assert easy.calls[0] == (msgs, {"max_tokens": 20})

    def test_records_decisions(self):
        client = RoutedClient(HeuristicRouter(threshold=1.0),
                              {EASY: FakeLLMClient(), HARD: FakeLLMClient()})
        client.chat([{"role": "user", "content": "hi"}])
        client.chat([{"role": "user", "content": "refactor it"}])
        assert client.last_decision.tier == HARD
        assert client.routed == {EASY: 1, HARD: 1}

    def test_needs_both_tiers(self):
        with pytest.raises(ValueError):
            RoutedClient(HeuristicRouter(), {EASY: FakeLLMClient()})

    def test_works_with_the_llm_router(self):
        hard = FakeLLMClient(["strong"])
        client = RoutedClient(LLMRouter(FakeLLMClient(["hard"])),
                              {EASY: FakeLLMClient(), HARD: hard})
        assert client.chat([{"role": "user", "content": "x"}]).text == "strong"
