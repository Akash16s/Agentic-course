"""Tests for Chapter 6b, Exercise 4 — reranking and query transformation."""

import json

import pytest

from agentlib.testing import FakeLLMClient
from chapters.ch06b_retrieval.exercises.exercise_4_rerank_and_rewrite import (
    LLMReranker,
    RerankResult,
    expand_query,
    multi_query_retrieve,
    parse_json,
    rewrite_followup,
)

CANDIDATES = [
    ("kb-01", "Payment errors: what each error means."),
    ("kb-02", "If the terminal shows E4012, the issuing bank refused the charge."),
    ("kb-03", "Error E4013 means the card has expired."),
]


def order(results):
    return [r.doc_id for r in results]


def scores(mapping):
    return json.dumps({"scores": mapping})


def reranker(*script, **kwargs):
    return LLMReranker(FakeLLMClient(list(script)), **kwargs)


class TestParseJson:
    def test_clean_json(self):
        assert parse_json('{"a": 1}') == {"a": 1}
        assert parse_json('["x", "y"]') == ["x", "y"]

    def test_inside_a_fence(self):
        assert parse_json('Here you go:\n```json\n{"a": 1}\n```\nHope that helps') == {"a": 1}
        assert parse_json('```\n["x"]\n```') == ["x"]

    def test_with_prose_either_side(self):
        assert parse_json('Sure! {"a": 1} Let me know.') == {"a": 1}
        assert parse_json('The queries are ["x", "y"] as requested') == ["x", "y"]

    def test_garbage_is_none_and_never_raises(self):
        for raw in [None, "", "   ", "no json here", "{broken", "[1, 2"]:
            assert parse_json(raw) is None, raw


class TestRerankerPrompt:
    def test_numbers_passages_by_position_not_doc_id(self):
        prompt = reranker().prompt("what is E4012", CANDIDATES)
        assert "what is E4012" in prompt
        assert "[0] Payment errors" in prompt
        assert "[2] Error E4013" in prompt
        assert "kb-01" not in prompt

    def test_truncates_long_passages(self):
        prompt = reranker(max_chars=10).prompt("q", [("x", "A" * 1000)])
        assert "A" * 10 in prompt
        assert "A" * 11 not in prompt

    def test_collapses_whitespace_and_separates_with_a_blank_line(self):
        prompt = reranker().prompt("q", [("x", "line one\n\n   line   two"), ("y", "second")])
        assert "[0] line one line two\n\n[1] second" in prompt


class TestRerankerParse:
    def test_wrapped_or_unwrapped(self):
        assert reranker().parse(scores({"0": 3, "1": 9}), 3) == {0: 3.0, 1: 9.0}
        assert reranker().parse('{"0": 3, "2": 7}', 3) == {0: 3.0, 2: 7.0}

    def test_bracketed_keys_and_string_scores(self):
        assert reranker().parse('{"scores": {"[1]": "6.5"}}', 3) == {1: 6.5}

    def test_clamps_to_zero_ten(self):
        assert reranker().parse(scores({"0": 15, "1": -3}), 3) == {0: 10.0, 1: 0.0}

    def test_skips_invented_passages(self):
        assert reranker().parse(scores({"0": 5, "7": 9}), 3) == {0: 5.0}

    def test_skips_bad_entries_but_keeps_good_ones(self):
        raw = '{"scores": {"0": "high", "x": 5, "1": true, "2": NaN, "3": null, "4": 4}}'
        assert reranker().parse(raw, 5) == {4: 4.0}

    def test_nothing_usable_is_none(self):
        for raw in ["I think passage 2 is best", '["not", "a", "dict"]',
                    '{"scores": [9, 2, 5]}', '{"scores": {"9": 5}}', ""]:
            assert reranker().parse(raw, 3) is None, raw


class TestRerank:
    def test_sorts_by_model_score(self):
        results = reranker(scores({"0": 2, "1": 9, "2": 5})).rerank("E4012", CANDIDATES)
        assert order(results) == ["kb-02", "kb-03", "kb-01"]
        top = results[0]
        assert isinstance(top, RerankResult)
        assert (top.score, top.text, top.original_rank) == (9.0, CANDIDATES[1][1], 1)

    def test_top_n(self):
        reply = scores({"0": 2, "1": 9, "2": 5})
        assert order(reranker(reply).rerank("q", CANDIDATES, top_n=1)) == ["kb-02"]
        assert len(reranker(reply).rerank("q", CANDIDATES, top_n=None)) == 3
        assert reranker(reply).rerank("q", CANDIDATES, top_n=-1) == []

    def test_ties_keep_original_order(self):
        results = reranker(scores({"0": 5, "1": 5, "2": 5})).rerank("q", CANDIDATES)
        assert order(results) == ["kb-01", "kb-02", "kb-03"]

    def test_unscored_candidates_go_last_in_original_order(self):
        results = reranker(scores({"2": 1})).rerank("q", CANDIDATES)
        assert order(results) == ["kb-03", "kb-01", "kb-02"]
        assert results[1].score is None

    def test_one_call_with_the_prompt_at_temperature_zero(self):
        client = FakeLLMClient([scores({"0": 1})])
        r = LLMReranker(client, max_tokens=99)
        r.rerank("E4012", CANDIDATES)
        assert client.call_count == 1
        messages, kwargs = client.calls[0]
        assert messages[-1]["content"] == r.prompt("E4012", CANDIDATES)
        assert (kwargs["temperature"], kwargs["max_tokens"]) == (0.0, 99)

    def test_model_is_passed_only_when_set(self):
        client = FakeLLMClient([scores({"0": 1}), scores({"0": 1})])
        LLMReranker(client).rerank("q", CANDIDATES)
        LLMReranker(client, model="cheap/model").rerank("q", CANDIDATES)
        assert "model" not in client.calls[0][1]
        assert client.calls[1][1]["model"] == "cheap/model"

    def test_zero_or_one_candidate_skips_the_model(self):
        client = FakeLLMClient()
        assert LLMReranker(client).rerank("q", []) == []
        single = LLMReranker(client).rerank("q", CANDIDATES[:1])
        assert order(single) == ["kb-01"] and single[0].score is None
        assert client.call_count == 0


class TestRerankFailsOpen:
    @pytest.mark.parametrize("reply", ["I'd say the second one.", TimeoutError("down")])
    def test_garbage_or_an_exception_keeps_the_original_order(self, reply):
        results = reranker(reply).rerank("q", CANDIDATES)
        assert order(results) == ["kb-01", "kb-02", "kb-03"]
        assert all(r.score is None for r in results)

    def test_fallbacks_are_counted(self):
        r = reranker("garbage", RuntimeError("boom"), scores({"0": 1}))
        assert r.fallbacks == 0
        for _ in range(3):
            r.rerank("q", CANDIDATES)
        assert r.fallbacks == 2

    def test_fallback_still_respects_top_n(self):
        assert order(reranker("garbage").rerank("q", CANDIDATES, top_n=2)) == ["kb-01", "kb-02"]


class TestExpandQuery:
    def test_original_first_then_rephrasings(self):
        client = FakeLLMClient(['["card rejected by bank", "E4012 decline meaning"]'])
        assert expand_query(client, "what is E4012", n=2) == [
            "what is E4012", "card rejected by bank", "E4012 decline meaning"]

    def test_accepts_a_queries_object_or_a_fence(self):
        assert expand_query(FakeLLMClient(['{"queries": ["refund timeline"]}']), "q", n=3) == \
            ["q", "refund timeline"]
        assert expand_query(FakeLLMClient(['```json\n["refund timeline"]\n```']), "q", n=1) == \
            ["q", "refund timeline"]

    def test_keeps_at_most_n(self):
        assert expand_query(FakeLLMClient(['["a", "b", "c", "d"]']), "q", n=2) == ["q", "a", "b"]

    def test_cleans_and_deduplicates(self):
        reply = '["What is  E4012", "card declined", "Card  Declined", "", 42, null, " a   b "]'
        assert expand_query(FakeLLMClient([reply]), "what is E4012", n=5) == [
            "what is E4012", "card declined", "a b"]

    def test_prompt_contains_the_query_and_n(self):
        client = FakeLLMClient(['["x"]'])
        expand_query(client, "what is E4012", n=4)
        prompt = client.last_messages[-1]["content"]
        assert "what is E4012" in prompt and "4" in prompt
        assert client.calls[0][1]["temperature"] == 0.0

    def test_n_zero_skips_the_model(self):
        client = FakeLLMClient()
        assert expand_query(client, "q", n=0) == ["q"]
        assert client.call_count == 0

    @pytest.mark.parametrize("reply", ["Sure: refunds", "{}", "[]", "", RuntimeError("down")])
    def test_garbage_or_an_exception_gives_back_the_original(self, reply):
        assert expand_query(FakeLLMClient([reply]), "q", n=3) == ["q"]


INDEX = {
    "refund policy": ["kb-04", "kb-01"],
    "money back": ["kb-08", "kb-04"],
    "chargeback": ["kb-11", "kb-04"],
}


class TestMultiQueryRetrieve:
    def test_fuses_the_rankings(self):
        found = multi_query_retrieve(list(INDEX), lambda q, k: INDEX[q], k=3)
        assert found[0] == "kb-04"  # every phrasing found it
        assert len(found) == 3
        everything = multi_query_retrieve(list(INDEX), lambda q, k: INDEX[q], k=10)
        assert set(everything) == {"kb-01", "kb-04", "kb-08", "kb-11"}

    def test_accepts_scored_rankings(self):
        assert multi_query_retrieve(["a", "b"], lambda q, k: [("x", 9.0), ("y", 1.0)], k=1) == ["x"]

    def test_per_query_fetch_size(self):
        seen = []
        fetch = lambda q, k: seen.append(k) or []  # noqa: E731
        multi_query_retrieve(["a", "b"], fetch, k=3)
        multi_query_retrieve(["a"], fetch, k=8)
        multi_query_retrieve(["a"], fetch, k=3, per_query=4)
        assert seen == [10, 10, 16, 4]

    def test_nothing_to_do(self):
        assert multi_query_retrieve([], lambda q, k: ["x"], k=3) == []
        assert multi_query_retrieve(["a"], lambda q, k: ["x"], k=0) == []


HISTORY = [
    {"role": "system", "content": "You are a support bot. SECRET-SYSTEM-PROMPT"},
    {"role": "user", "content": "compare the Starter and Pro plans"},
    {"role": "assistant", "content": "Starter is $10/month. Pro is $30/month with SSO."},
]


class TestRewriteFollowup:
    def test_sends_the_conversation_and_returns_the_rewrite(self):
        client = FakeLLMClient(["Pro plan usage limits"])
        assert rewrite_followup(client, HISTORY, "what about the second one's limits?") == \
            "Pro plan usage limits"
        prompt = client.last_messages[-1]["content"]
        assert "user: compare the Starter and Pro plans" in prompt
        assert "assistant: Starter is $10/month" in prompt
        assert "what about the second one's limits?" in prompt
        assert client.calls[0][1]["temperature"] == 0.0

    def test_no_history_skips_the_model(self):
        client = FakeLLMClient()
        assert rewrite_followup(client, [], "how do refunds work?") == "how do refunds work?"
        assert rewrite_followup(client, HISTORY[:1], "q") == "q"  # a system prompt alone
        assert client.call_count == 0

    def test_system_and_tool_messages_are_left_out(self):
        client = FakeLLMClient(["x"])
        history = HISTORY + [{"role": "tool", "content": "TOOL-OUTPUT"},
                             {"role": "assistant", "content": None}]
        rewrite_followup(client, history, "q")
        prompt = client.last_messages[-1]["content"]
        assert "SECRET-SYSTEM-PROMPT" not in prompt
        assert "TOOL-OUTPUT" not in prompt

    def test_keeps_only_the_last_turns(self):
        client = FakeLLMClient(["x"])
        history = [{"role": "user", "content": f"turn-{i}"} for i in range(10)]
        rewrite_followup(client, history, "q", max_turns=3)
        prompt = client.last_messages[-1]["content"]
        assert "turn-9" in prompt and "turn-7" in prompt
        assert "turn-6" not in prompt

    @pytest.mark.parametrize("reply", [
        '"Pro plan usage limits"',
        "'Pro plan usage limits'",
        "Standalone query: Pro plan usage limits",
        "\n\n  Pro plan usage limits  \nThis resolves 'the second one'.",
    ])
    def test_cleans_the_reply(self, reply):
        assert rewrite_followup(FakeLLMClient([reply]), HISTORY, "q") == "Pro plan usage limits"

    @pytest.mark.parametrize("reply", [
        "   ",
        "The Pro plan includes " + "lots of features " * 50,  # answered, not rewritten
        RuntimeError("down"),
    ])
    def test_falls_back_to_the_original_question(self, reply):
        assert rewrite_followup(FakeLLMClient([reply]), HISTORY, "orig") == "orig"
