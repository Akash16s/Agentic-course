"""SOLUTION — Chapter 6b, Exercise 4."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .exercise_3_hybrid import reciprocal_rank_fusion


_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def parse_json(raw: str | None) -> Any | None:
    """The first JSON value found in a model reply. None on failure; never raises.

    Tries, in order: the whole reply, the inside of a ``` fence, the widest {...}
    span, the widest [...] span.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    candidates = [text, *(block.strip() for block in _FENCE.findall(text))]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            candidates.append(text[start: end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


RERANK_PROMPT = """\
You are ranking search results. Score how well each passage answers the query.

QUERY: {query}

PASSAGES:
{passages}

Score every passage from 0 (irrelevant) to 10 (directly answers the query).
Judge only relevance to the query, not writing quality.

Return ONLY JSON, one entry per passage number:
{{"scores": {{"0": <0-10>, "1": <0-10>, ...}}}}"""


@dataclass
class RerankResult:
    """One reranked candidate. `score` is None when the model gave it no score."""

    doc_id: str
    text: str
    score: float | None
    original_rank: int


def _chat_text(client: Any, prompt: str, *, model: str | None, max_tokens: int) -> str:
    kwargs: dict[str, Any] = {"temperature": 0.0, "max_tokens": max_tokens}
    if model is not None:
        kwargs["model"] = model
    return client.chat([{"role": "user", "content": prompt}], **kwargs).text


class LLMReranker:
    """Ask a model to score (query, passage) pairs, then sort by that score.

    This is a cross-encoder built out of a chat model: the model reads the query and
    each passage TOGETHER, which is what makes it more accurate than comparing two
    independently computed embeddings — and what makes it far too slow to run over
    your whole corpus. So: retrieve wide (~50), rerank narrow (~5).

    FAILS OPEN. Reranking is an improvement on an order you already have. If the
    model returns garbage or the call errors, you return the original order and count
    a fallback — you do not fail the user's request over an optimisation.
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str | None = None,
        max_chars: int = 500,
        max_tokens: int = 512,
    ) -> None:
        self.client = client
        self.model = model
        self.max_chars = max_chars
        self.max_tokens = max_tokens
        self.fallbacks = 0

    def prompt(self, query: str, candidates: Sequence[tuple[str, str]]) -> str:
        passages = "\n\n".join(
            f"[{i}] {' '.join(text.split())[: self.max_chars]}"
            for i, (_, text) in enumerate(candidates)
        )
        return RERANK_PROMPT.format(query=query, passages=passages)

    def parse(self, raw: str | None, n: int) -> dict[int, float] | None:
        """{index: score} for the valid entries, or None if nothing usable came back."""
        obj = parse_json(raw)
        if not isinstance(obj, dict):
            return None
        scores = obj.get("scores", obj)
        if not isinstance(scores, dict):
            return None
        parsed: dict[int, float] = {}
        for key, value in scores.items():
            try:
                index = int(str(key).strip().strip("[]"))
                if isinstance(value, bool):
                    raise TypeError("a bool is not a score")
                score = float(value)
            except (TypeError, ValueError):
                continue
            if 0 <= index < n and math.isfinite(score):
                parsed[index] = min(10.0, max(0.0, score))
        return parsed or None

    def rerank(
        self,
        query: str,
        candidates: Sequence[tuple[str, str]],
        top_n: int | None = 5,
    ) -> list[RerankResult]:
        candidates = list(candidates)
        limit = len(candidates) if top_n is None else max(0, top_n)
        if len(candidates) <= 1:
            return [RerankResult(d, t, None, i) for i, (d, t) in enumerate(candidates)][:limit]

        try:
            raw = _chat_text(self.client, self.prompt(query, candidates),
                             model=self.model, max_tokens=self.max_tokens)
            scores = self.parse(raw, len(candidates))
        except Exception:  # noqa: BLE001 - fail open on anything
            scores = None

        if scores is None:
            self.fallbacks += 1
            scores = {}

        results = [
            RerankResult(doc_id, text, scores.get(i), i)
            for i, (doc_id, text) in enumerate(candidates)
        ]
        # scored first, by score; unscored after, in their original order
        results.sort(key=lambda r: (r.score is None, -(r.score or 0.0), r.original_rank))
        return results[:limit]


# ======================================================= query transformation


EXPAND_PROMPT = """\
Write {n} different search queries that would find documents answering the question
below. Use different wording and synonyms; keep each one short. Do not answer it.

QUESTION: {query}

Return ONLY a JSON array of {n} strings."""


def _normalise_query(text: str) -> str:
    return " ".join(text.lower().split())


def expand_query(client: Any, query: str, n: int = 3, *, model: str | None = None) -> list[str]:
    """[query] + up to n alternative phrasings. Always starts with the original.

    Fails safe: garbage, an empty reply or an exception gives back [query].
    """
    if n <= 0:
        return [query]
    try:
        raw = _chat_text(client, EXPAND_PROMPT.format(n=n, query=query),
                         model=model, max_tokens=300)
    except Exception:  # noqa: BLE001
        return [query]

    parsed = parse_json(raw)
    if isinstance(parsed, dict):
        parsed = parsed.get("queries")
    if not isinstance(parsed, list):
        return [query]

    out = [query]
    seen = {_normalise_query(query)}
    for item in parsed:
        if not isinstance(item, str):
            continue
        cleaned = " ".join(item.split())
        key = _normalise_query(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) == n + 1:
            break
    return out


def multi_query_retrieve(
    queries: Sequence[str],
    retrieve_fn: Callable[[str, int], Sequence[Any]],
    k: int = 5,
    *,
    per_query: int | None = None,
    rrf_k: int = 60,
) -> list[str]:
    """Run every query, fuse the rankings with RRF, return the top k ids."""
    if k <= 0 or not queries:
        return []
    per_query = per_query or max(k * 2, 10)
    rankings = [list(retrieve_fn(q, per_query)) for q in queries]
    return [doc_id for doc_id, _ in reciprocal_rank_fusion(rankings, k=rrf_k)[:k]]


REWRITE_PROMPT = """\
Rewrite the user's latest message as a single standalone search query. Resolve every
pronoun and reference ("it", "that one", "the second one") using the conversation.
Do not answer it. If it is already standalone, return it unchanged.

CONVERSATION:
{history}

LATEST MESSAGE: {question}

Return ONLY the rewritten query, on one line."""

#: Labels models like to put in front of the answer despite being told not to.
LABEL = re.compile(r"^(standalone (search )?(query|question)|rewritten( query)?|query)\s*:\s*",
                    re.IGNORECASE)


def rewrite_followup(
    client: Any,
    history: Sequence[dict[str, Any]],
    question: str,
    *,
    max_turns: int = 6,
    max_chars: int = 500,
    model: str | None = None,
) -> str:
    """Turn a follow-up into a query that makes sense with no conversation around it.

    "what about the second one?" embeds as nothing in particular. After rewriting it
    is "pricing of the Pro plan", which retrieves. Fails safe to the original question.
    """
    turns = [
        m for m in history
        if m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str) and m["content"].strip()
    ]
    turns = turns[-max_turns:] if max_turns > 0 else []
    if not turns:
        return question

    transcript = "\n".join(f"{m['role']}: {m['content'].strip()}" for m in turns)
    try:
        raw = _chat_text(client, REWRITE_PROMPT.format(history=transcript, question=question),
                         model=model, max_tokens=200)
    except Exception:  # noqa: BLE001
        return question

    lines = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not lines:
        return question
    text = LABEL.sub("", lines[0]).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'`":
        text = text[1:-1].strip()
    if not text or len(text) > max_chars:
        return question
    return text
