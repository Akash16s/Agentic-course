"""SOLUTION — Chapter 13b, Exercise 3."""

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
    tier: str                                   # EASY or HARD
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


HARD_KEYWORDS: tuple[str, ...] = (
    "prove", "step by step", "refactor", "debug", "derive",
    "optimise", "optimize", "architecture", "trade-off", "edge case",
)


class HeuristicRouter:
    def __init__(self, *, threshold: float = 2.0, long_chars: int = 2000,
                 keywords: tuple[str, ...] = HARD_KEYWORDS) -> None:
        self.threshold = threshold
        self.long_chars = long_chars
        self.keywords = keywords

    def features(self, text: str) -> dict[str, Any]:
        lowered = text.lower()
        return {
            "length": len(text),
            "code_blocks": text.count("```") // 2,
            "keywords": [k for k in self.keywords if k in lowered],
            "questions": text.count("?"),
        }

    def route(self, text: str) -> RouteDecision:
        f = self.features(text)
        score = 0.0
        reasons: list[str] = []
        if f["length"] >= self.long_chars:
            score += 1.0
            reasons.append(f"long input ({f['length']:,} chars)")
        if f["code_blocks"] >= 1:
            score += 1.0
            reasons.append(f"{f['code_blocks']} code block(s)")
        if f["keywords"]:
            score += min(1.0 * len(f["keywords"]), 2.0)
            reasons.extend(f"keyword: {k}" for k in f["keywords"])
        if f["questions"] > 1:
            score += min(0.5 * (f["questions"] - 1), 1.0)
            reasons.append(f"{f['questions']} questions")
        tier = HARD if score >= self.threshold else EASY
        return RouteDecision(tier=tier, score=score, reasons=reasons)


CLASSIFY_PROMPT = """Classify how hard this task is for an AI assistant.

easy: lookup, short factual answer, simple rewrite, formatting, classification.
hard: multi-step reasoning, maths, non-trivial code, careful analysis, planning.

TASK:
{task}

Reply with exactly one word: easy or hard."""


def parse_label(reply: str) -> str | None:
    words = set(re.findall(r"[a-z]+", (reply or "").lower()))
    found = [label for label in (EASY, HARD) if label in words]
    return found[0] if len(found) == 1 else None


def _score(tier: str) -> float:
    return 1.0 if tier == HARD else 0.0


class LLMRouter:
    def __init__(self, client: Any, *, default: str = HARD,
                 max_chars: int = 2000) -> None:
        if default not in (EASY, HARD):
            raise ValueError(f"default must be {EASY!r} or {HARD!r}")
        self.client = client
        self.default = default
        self.max_chars = max_chars
        self.total_usage = Usage()
        self.calls = 0

    def route(self, text: str) -> RouteDecision:
        prompt = CLASSIFY_PROMPT.format(task=text[: self.max_chars])
        try:
            response = self.client.chat([{"role": "user", "content": prompt}],
                                        temperature=0.0, max_tokens=5)
        except errors.LLMError as exc:
            return RouteDecision(self.default, _score(self.default),
                                 [f"router error, defaulted: {exc!r}"])
        self.calls += 1
        self.total_usage = self.total_usage + response.usage
        label = parse_label(response.text)
        if label is None:
            return RouteDecision(self.default, _score(self.default),
                                 [f"unparseable reply, defaulted: {response.text!r}"])
        return RouteDecision(label, _score(label), [f"llm said {label}"])


def last_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""


class RoutedClient:
    def __init__(self, router: Any, clients: dict[str, Any]) -> None:
        missing = {EASY, HARD} - set(clients)
        if missing:
            raise ValueError(f"RoutedClient needs a client for: {sorted(missing)}")
        self.router = router
        self.clients = dict(clients)
        self.last_decision: RouteDecision | None = None
        self.routed: Counter[str] = Counter()

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        decision = self.router.route(last_user_text(messages))
        self.last_decision = decision
        self.routed[decision.tier] += 1
        return self.clients[decision.tier].chat(messages, **kwargs)
