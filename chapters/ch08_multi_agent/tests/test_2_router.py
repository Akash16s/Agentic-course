"""Tests for Chapter 8, Exercise 2 — routing."""

import pytest

from chapters.ch08_multi_agent.exercises.exercise_2_router import Route, Router

ROUTES = [
    Route("billing", "payments, invoices and refunds", when_not="technical bugs"),
    Route("technical", "bugs, outages and errors"),
    Route("general", "anything else"),
]


class TestConstruction:
    def test_requires_routes(self):
        with pytest.raises(ValueError):
            Router([])

    def test_default_is_the_first_route(self):
        assert Router(ROUTES).default == "billing"

    def test_explicit_default(self):
        assert Router(ROUTES, default="general").default == "general"


class TestPrompt:
    def test_includes_every_route(self):
        prompt = Router(ROUTES).prompt("my card was declined")
        for route in ROUTES:
            assert route.name in prompt

    def test_includes_descriptions(self):
        assert "invoices" in Router(ROUTES).prompt("q")

    def test_includes_when_not(self):
        assert "technical bugs" in Router(ROUTES).prompt("q")

    def test_includes_the_query(self):
        assert "my card was declined" in Router(ROUTES).prompt("my card was declined")

    def test_stays_short(self):
        # this runs on every request; it should be cheap
        assert len(Router(ROUTES).prompt("q")) < 800


class TestParse:
    def test_exact_match(self):
        assert Router(ROUTES).parse("billing") == "billing"

    def test_case_insensitive(self):
        assert Router(ROUTES).parse("BILLING") == "billing"

    def test_whitespace(self):
        assert Router(ROUTES).parse("  technical \n") == "technical"

    def test_name_inside_a_sentence(self):
        # you ask for one word; you get this about a third of the time
        assert Router(ROUTES).parse("I'd route this to billing.") == "billing"

    def test_markdown_wrapping(self):
        assert Router(ROUTES).parse("**technical**") == "technical"

    def test_unrecognised_falls_back_to_the_default(self):
        assert Router(ROUTES).parse("no idea, sorry") == "billing"

    def test_empty_falls_back(self):
        assert Router(ROUTES).parse("") == "billing"
        assert Router(ROUTES).parse(None) == "billing"

    def test_never_raises(self):
        router = Router(ROUTES)
        for raw in ["", None, "???", "billing technical general", "{}"]:
            assert router.parse(raw) in {"billing", "technical", "general"}


class TestRoute:
    def test_end_to_end(self):
        seen = []

        def call(prompt):
            seen.append(prompt)
            return "technical"

        assert Router(ROUTES).route("the site is down", call) == "technical"
        assert "the site is down" in seen[0]

    def test_bad_model_output_still_routes(self):
        assert Router(ROUTES).route("q", lambda p: "I cannot help") == "billing"
