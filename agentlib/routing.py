"""Model routing — the right model for each request, and a plan for when it is down.

Promoted from Chapter 13b.

Chapter 13 made one provider survivable. This is the next step: more than one
model. Fallback chains for when a model is down, rules for which models CAN serve
a request, routers that guess which models SHOULD, and cascades that try cheap
first and check the answer before paying for strong. None of it is clever. All of
it is the difference between a bill you planned and a bill you discovered.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from agentlib import errors
from agentlib.hardening import CircuitBreaker, CircuitOpen
from agentlib.llm import LLMResponse, Message, Usage
from agentlib.pricing import cost_usd
from agentlib.retry import chat_with_retry

# ------------------------------------------------------------------ fallback


@dataclass
class Attempt:
    """One model's turn in a fallback chain."""

    model: str                              # the NAME from the chain, not response.model
    ok: bool = False
    error: errors.LLMError | None = None
    skipped: bool = False                   # breaker open: never called at all


class AllModelsFailed(errors.LLMError):
    """Every model in the chain failed (or was skipped). Carries every attempt.

    Not retryable: the chain WAS the retry. An outer retry around a whole chain
    multiplies your traffic by the chain length during exactly the moment every
    provider is struggling.
    """

    retryable = False

    def __init__(self, attempts: list[Attempt]) -> None:
        parts = []
        for a in attempts:
            what = "skipped (breaker open)" if a.skipped else repr(a.error)
            parts.append(f"{a.model}: {what}")
        super().__init__("all models failed -> " + "; ".join(parts))
        self.attempts = attempts

    @property
    def errors(self) -> list[errors.LLMError]:
        return [a.error for a in self.attempts if a.error is not None]


class FallbackClient:
    """Try models in order. Fall through on THEIR problems, stop on YOURS.

    * retryable error (429, 5xx, timeout, connection) -> next model
    * non-retryable error (400, 401, 404)              -> re-raise immediately:
      a malformed request fails on every model, and a bad key is your bug
    * breaker open for a model                          -> skip it without calling
    """

    def __init__(
        self,
        clients: list[tuple[str, Any]],
        *,
        breakers: dict[str, CircuitBreaker] | None = None,
        attempts_per_model: int = 1,
        base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not clients:
            raise ValueError("a fallback chain needs at least one client")
        names = [name for name, _ in clients]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate model names in chain: {names}")
        self.clients = list(clients)
        self.breakers = dict(breakers or {})
        self.attempts_per_model = attempts_per_model
        self.base_delay = base_delay
        self.sleep = sleep
        self.last_attempts: list[Attempt] = []
        self.answered_by: str | None = None
        self.served_by: Counter[str] = Counter()

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        attempts: list[Attempt] = []
        self.last_attempts = attempts
        self.answered_by = None

        for name, client in self.clients:
            breaker = self.breakers.get(name)
            if breaker is not None and not breaker.allow():
                attempts.append(Attempt(
                    model=name, skipped=True,
                    error=CircuitOpen(f"{name}: circuit open, skipped")))
                continue
            try:
                response = chat_with_retry(
                    client, messages,
                    max_attempts=self.attempts_per_model,
                    base_delay=self.base_delay,
                    sleep=self.sleep,
                    **kwargs,
                )
            except errors.LLMError as exc:
                if not exc.retryable:
                    # your bug, not their outage: do not blame the breaker either
                    attempts.append(Attempt(model=name, error=exc))
                    raise
                if breaker is not None:
                    breaker.record_failure()
                attempts.append(Attempt(model=name, error=exc))
                continue
            if breaker is not None:
                breaker.record_success()
            attempts.append(Attempt(model=name, ok=True))
            self.answered_by = name
            self.served_by[name] += 1
            return response

        raise AllModelsFailed(attempts)


# ------------------------------------------------------------- static rules


@dataclass(frozen=True)
class ModelSpec:
    """What you know about a model before you call it."""

    name: str
    context_window: int          # total tokens: input + output
    price_in: float              # $ per MILLION input tokens
    price_out: float             # $ per MILLION output tokens
    supports_tools: bool = True
    supports_vision: bool = False
    tier: int = 1                # 1 = small/cheap, 2 = mid, 3 = frontier


class NoModelFits(errors.BadRequestError):
    """No configured model can serve this request. Says why, per model.

    A BadRequestError on purpose: no amount of retrying or falling back fixes a
    request that is too long for every model you have.
    """

    def __init__(self, reasons: dict[str, str]) -> None:
        detail = "; ".join(f"{k}: {v}" for k, v in reasons.items()) or "no models"
        super().__init__(f"no model fits -> {detail}")
        self.reasons = reasons


#: Static routing by task type: the lowest tier each kind of task may use.
TASK_MIN_TIER: dict[str, int] = {
    "classify": 1,
    "extract": 1,
    "summarise": 1,
    "chat": 1,
    "code": 2,
    "plan": 2,
    "reason": 3,
}


def estimate_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    """Dollar cost of one call on `spec`."""
    return (input_tokens * spec.price_in + output_tokens * spec.price_out) / 1_000_000


def fits_context(spec: ModelSpec, input_tokens: int, output_tokens: int) -> bool:
    """Input AND the reply you want must fit. Leaving no room for the answer is
    the classic version of this bug: the request is accepted and the reply is
    truncated at 3 tokens."""
    return input_tokens + output_tokens <= spec.context_window


def select_model(
    specs: list[ModelSpec],
    *,
    input_tokens: int,
    output_tokens: int = 1024,
    needs_tools: bool = False,
    needs_vision: bool = False,
    min_tier: int = 1,
    max_tier: int | None = None,
) -> ModelSpec:
    """The cheapest model that CAN serve this request. Raises NoModelFits."""
    reasons: dict[str, str] = {}
    capable: list[ModelSpec] = []
    for spec in specs:
        if needs_tools and not spec.supports_tools:
            reasons[spec.name] = "no tool support"
        elif needs_vision and not spec.supports_vision:
            reasons[spec.name] = "no vision support"
        elif spec.tier < min_tier:
            reasons[spec.name] = f"tier {spec.tier} below min_tier {min_tier}"
        elif max_tier is not None and spec.tier > max_tier:
            reasons[spec.name] = f"tier {spec.tier} above max_tier {max_tier}"
        elif not fits_context(spec, input_tokens, output_tokens):
            reasons[spec.name] = (
                f"context {spec.context_window:,} < "
                f"{input_tokens:,} in + {output_tokens:,} out")
        else:
            capable.append(spec)
    if not capable:
        raise NoModelFits(reasons)
    # min() is stable: on a full tie the first-listed wins
    return min(capable,
               key=lambda s: (estimate_cost(s, input_tokens, output_tokens), s.tier))


def select_for_task(specs: list[ModelSpec], task: str, **kwargs: Any) -> ModelSpec:
    """select_model with min_tier looked up from TASK_MIN_TIER (unknown task -> 1)."""
    return select_model(specs, min_tier=TASK_MIN_TIER.get(task, 1), **kwargs)


# ------------------------------------------------------------------ routers


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
    """Guess difficulty from cheap surface features. Free, instant, and wrong
    sometimes — which is fine if you measure how often.

    score = +1.0 if len(text) >= long_chars
          + 1.0 if there is at least one fenced code block
          + 1.0 per distinct hard keyword found, capped at 2.0
          + 0.5 per question mark beyond the first, capped at 1.0
    tier  = HARD if score >= threshold else EASY
    """

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
    """'easy' / 'hard' if exactly ONE of them appears as a whole word, else None."""
    words = set(re.findall(r"[a-z]+", (reply or "").lower()))
    found = [label for label in (EASY, HARD) if label in words]
    return found[0] if len(found) == 1 else None


class LLMRouter:
    """Ask a small model to classify. Falls back to `default` when it can't tell.

    The default is HARD, deliberately: mis-routing is asymmetric. An easy task on
    the strong model wastes cents; a hard task on the weak model is a wrong
    answer shown to a user.
    """

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


def _score(tier: str) -> float:
    return 1.0 if tier == HARD else 0.0


def last_user_text(messages: list[Message]) -> str:
    """The text of the last user message ('' if none)."""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""


class RoutedClient:
    """A client that routes each request to `clients[decision.tier]`."""

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


# ------------------------------------------------------------------ cascade


@dataclass
class CascadeStep:
    model: str
    output: str = ""
    accepted: bool = False
    cost: float = 0.0
    error: str | None = None


@dataclass
class CascadeResult:
    output: str
    model: str                       # tier whose output we are returning
    accepted: bool                   # False: even the last tier failed the check
    steps: list[CascadeStep] = field(default_factory=list)
    total_cost: float = 0.0

    @property
    def escalations(self) -> int:
        return max(len(self.steps) - 1, 0)


def response_cost(name: str, response: LLMResponse) -> float:
    """Default cost function: price response.model (or the tier name)."""
    u = response.usage
    return cost_usd(response.model or name, u.prompt_tokens, u.completion_tokens)


class Cascade:
    """Try cheap first; CHECK the answer; escalate only if the check fails.

    The check must be something you can verify — a schema, a test run, a judge.
    Asking the model "are you sure?" measures its confidence, not its correctness.
    """

    def __init__(
        self,
        tiers: list[tuple[str, Any]],
        accept: Callable[[str], bool],
        *,
        cost_fn: Callable[[str, LLMResponse], float] = response_cost,
    ) -> None:
        if not tiers:
            raise ValueError("a cascade needs at least one tier")
        self.tiers = list(tiers)
        self.accept = accept
        self.cost_fn = cost_fn

    def _accepts(self, response: LLMResponse) -> bool:
        if response.truncated:
            return False                       # a cut-off answer is not an answer
        try:
            return bool(self.accept(response.text))
        except Exception:  # noqa: BLE001 - a validator crashing on garbage = reject
            return False

    def run(self, messages: list[Message], **kwargs: Any) -> CascadeResult:
        steps: list[CascadeStep] = []
        last_ok: CascadeStep | None = None
        last_error: errors.LLMError | None = None

        for name, client in self.tiers:
            try:
                response = client.chat(messages, **kwargs)
            except errors.LLMError as exc:
                if not exc.retryable:
                    raise
                steps.append(CascadeStep(model=name, error=repr(exc)))
                last_error = exc
                continue
            step = CascadeStep(model=name, output=response.text,
                               cost=self.cost_fn(name, response))
            step.accepted = self._accepts(response)
            steps.append(step)
            last_ok = step
            if step.accepted:
                break

        if last_ok is None:
            assert last_error is not None
            raise last_error
        return CascadeResult(
            output=last_ok.output,
            model=last_ok.model,
            accepted=last_ok.accepted,
            steps=steps,
            total_cost=sum(s.cost for s in steps),
        )


def expected_cost(p_accept_cheap: float, cost_cheap: float, cost_strong: float) -> float:
    """p * c_cheap + (1 - p) * (c_cheap + c_strong). You ALWAYS pay for cheap."""
    if not 0.0 <= p_accept_cheap <= 1.0:
        raise ValueError("p_accept_cheap must be between 0 and 1")
    return cost_cheap + (1.0 - p_accept_cheap) * cost_strong


def break_even_accept_rate(cost_cheap: float, cost_strong: float) -> float:
    """The accept rate at which a 2-tier cascade costs the same as strong-only.

    c_cheap + (1 - p) * c_strong == c_strong  ->  p = c_cheap / c_strong.
    Above 1.0 means the cascade can never win.
    """
    if cost_strong <= 0:
        raise ValueError("cost_strong must be positive")
    return cost_cheap / cost_strong


def savings_vs_strong(p_accept_cheap: float, cost_cheap: float,
                      cost_strong: float) -> float:
    """Fraction saved vs always using strong. Negative means the cascade LOSES."""
    return 1.0 - expected_cost(p_accept_cheap, cost_cheap, cost_strong) / cost_strong


def expected_cost_chain(costs: list[float], accept_rates: list[float]) -> float:
    """Expected cost of an N-tier cascade.

    accept_rates[i] is the chance tier i's answer passes GIVEN the request reached
    tier i. There is one fewer rate than costs: the last tier is final.
    """
    if not costs:
        raise ValueError("need at least one tier")
    if len(accept_rates) != len(costs) - 1:
        raise ValueError("need exactly len(costs) - 1 accept rates")
    if any(not 0.0 <= p <= 1.0 for p in accept_rates):
        raise ValueError("accept rates must be between 0 and 1")
    total = 0.0
    p_reach = 1.0
    for i, cost in enumerate(costs):
        total += p_reach * cost
        if i < len(accept_rates):
            p_reach *= 1.0 - accept_rates[i]
    return total
