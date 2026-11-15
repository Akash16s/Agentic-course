"""EXERCISE 3 — Dynamic routing: which model SHOULD serve this request?

    pytest chapters/ch13b_routing/tests -q -k router
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from agentlib import errors
from agentlib.llm import LLMResponse, Message, Usage

EASY = "easy"
HARD = "hard"


@dataclass
class RouteDecision:
    """(Given.) What a router decided, and why — log the reasons."""

    tier: str                                   # EASY or HARD
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


#: (Given.) Words that tend to mean "this needs the strong model".
HARD_KEYWORDS: tuple[str, ...] = (
    "prove", "step by step", "refactor", "debug", "derive",
    "optimise", "optimize", "architecture", "trade-off", "edge case",
)


class HeuristicRouter:
    """Guess difficulty from cheap surface features. Free, instant, and wrong
    sometimes — which is fine, as long as you measure how often (exercise 5).

    __init__(self, *, threshold=2.0, long_chars=2000, keywords=HARD_KEYWORDS)
    """

    def __init__(self, *, threshold: float = 2.0, long_chars: int = 2000,
                 keywords: tuple[str, ...] = HARD_KEYWORDS) -> None:
        # TODO: implement
        raise NotImplementedError

    def features(self, text: str) -> dict[str, Any]:
        """Return exactly these four keys:

            "length":      len(text)
            "code_blocks": text.count("```") // 2   (a block is an opening + closing fence)
            "keywords":    list of the self.keywords that appear in text,
                           CASE-INSENSITIVE, in self.keywords order
            "questions":   text.count("?")
        """
        # TODO: implement
        raise NotImplementedError

    def route(self, text: str) -> RouteDecision:
        """Score the features, then pick a tier. The weights, exactly:

            +1.0  if length >= long_chars              reason: "long input (...)"
            +1.0  if code_blocks >= 1                  reason: "... code block(s)"
            +1.0  per keyword found, capped at 2.0     reason: "keyword: <kw>" (one each)
            +0.5  per question mark BEYOND the first,
                  capped at 1.0                        reason: "<n> questions"

            tier = HARD if score >= self.threshold else EASY

        Return RouteDecision(tier, score, reasons). No features -> EASY, 0.0, [].

        The caps matter: without them, one prompt that says "debug" five times
        outvotes everything else. The reasons matter more: when a user complains
        about a bad answer, "routed EASY, score 1.0, reasons ['keyword: debug']"
        tells you what happened in one log line.
        """
        # TODO: implement
        raise NotImplementedError


#: (Given.) The classification prompt. Note it DEFINES easy and hard: a small
#: model asked "is this hard?" with no definition answers by vibes.
CLASSIFY_PROMPT = """Classify how hard this task is for an AI assistant.

easy: lookup, short factual answer, simple rewrite, formatting, classification.
hard: multi-step reasoning, maths, non-trivial code, careful analysis, planning.

TASK:
{task}

Reply with exactly one word: easy or hard."""


def parse_label(reply: str) -> str | None:
    """EASY or HARD if exactly ONE of them appears as a WHOLE WORD, else None.

        "easy"                  -> "easy"
        "HARD."                 -> "hard"
        "**easy**"              -> "easy"
        "The task is hard"      -> "hard"
        "easy or hard"          -> None   (both: the model hedged)
        "medium" / ""           -> None
        "hardly" / "uneasy"     -> None   (substrings are not words)

    Hint: re.findall(r"[a-z]+", reply.lower()) gives you the words.

    Compare Chapter 8's Router.parse, which matches substrings. That was fine for
    route names like "billing"; it is not fine here, where "hardly anything to do"
    would route to the expensive model.
    """
    # TODO: implement
    raise NotImplementedError


class LLMRouter:
    """Ask a small model to classify. Falls back to `default` when it can't tell.

    __init__(self, client, *, default=HARD, max_chars=2000)
      default not in (EASY, HARD) -> ValueError
      also keep: self.total_usage = Usage()  and  self.calls = 0

    THE DEFAULT IS HARD, deliberately. Mis-routing is asymmetric: an easy task on
    the strong model wastes a cent; a hard task on the weak model is a wrong
    answer in front of a user. When unsure, spend.
    """

    def __init__(self, client: Any, *, default: str = HARD,
                 max_chars: int = 2000) -> None:
        # TODO: implement
        raise NotImplementedError

    def route(self, text: str) -> RouteDecision:
        """Spec:
          1. prompt = CLASSIFY_PROMPT.format(task=text[:self.max_chars])
             (the router reads the first max_chars only — the router is a model
              call too, and paying to classify 50k tokens defeats the point)
          2. self.client.chat([{"role": "user", "content": prompt}],
                              temperature=0.0, max_tokens=5)
          3. it raised errors.LLMError -> RouteDecision(self.default, ...) with a
             reason mentioning "error". A router outage must not become an
             outage of the thing it routes.
          4. success: self.calls += 1; add response.usage to self.total_usage
          5. label = parse_label(response.text); None -> self.default, with a
             reason mentioning "unparseable"
          6. return RouteDecision(label, score, [reason])
             score: 1.0 for HARD, 0.0 for EASY (defaults too).
        """
        # TODO: implement
        raise NotImplementedError


def last_user_text(messages: list[Message]) -> str:
    """The content of the LAST message with role "user"; "" if there is none or
    its content is not a string (e.g. a multimodal list)."""
    # TODO: implement
    raise NotImplementedError


class RoutedClient:
    """A client that routes each request: clients[router.route(text).tier].chat(...)

    __init__(self, router, clients: dict[str, client])
      clients must have BOTH EASY and HARD keys, else ValueError
      also keep: self.last_decision = None  and  self.routed = Counter()

    `router` is anything with .route(text) -> RouteDecision: HeuristicRouter,
    LLMRouter, or your own.
    """

    def __init__(self, router: Any, clients: dict[str, Any]) -> None:
        # TODO: implement
        raise NotImplementedError

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Route on last_user_text(messages), record last_decision, bump
        routed[tier], then forward messages and kwargs UNCHANGED to the chosen
        client and return its response."""
        # TODO: implement
        raise NotImplementedError
