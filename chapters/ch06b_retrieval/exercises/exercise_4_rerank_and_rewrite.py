"""EXERCISE 4 — Reranking with a model, and rewriting the query before you search.

    pytest chapters/ch06b_retrieval/tests -q -k rerank_and_rewrite

Every function that talks to a model takes a `client` with Chapter 1's interface:

    client.chat([{"role": "user", "content": prompt}], temperature=0.0,
                max_tokens=..., model=...)  ->  LLMResponse  (use `.text`)

Pass `model=` ONLY when one was given (not None). The tests use
`agentlib.testing.FakeLLMClient`, which records every call so they can check what
you sent.

The common thread: all of these are OPTIMISATIONS on a retrieval you already have.
So none of them may make things worse when the model misbehaves. Garbage in the
reply, an exception from the client — you fall back to what you had before.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .exercise_3_hybrid import reciprocal_rank_fusion


def parse_json(raw: str | None) -> Any | None:
    """The first JSON value found in a model reply. None on failure; NEVER raises.

    Try these candidates in order and return the first that `json.loads` accepts:
      1. the whole reply, stripped
      2. the inside of each ``` fence (```json ... ``` or plain ``` ... ```)
      3. the widest {...} span (first "{" to last "}")
      4. the widest [...] span (first "[" to last "]")

    None, "" or whitespace -> None. Models wrap JSON in prose and fences constantly,
    even when told "ONLY JSON"; a parser that needs a perfect reply is a parser that
    fails in production.
    """
    # TODO: implement
    raise NotImplementedError


# ================================================================ reranking


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
    """One reranked candidate. `score` is None when the model gave it no usable score.

    `original_rank` is its 0-based position in the list you were given.
    """

    doc_id: str
    text: str
    score: float | None
    original_rank: int


class LLMReranker:
    """Ask a model to score each (query, passage) pair, then sort by that score.

    __init__(self, client, *, model=None, max_chars=500, max_tokens=512)
      Store all four, plus `self.fallbacks = 0` — a counter of how many times you
      had to fall back to the original order. In production you alert on it: a
      reranker that silently fell back on every call for a week looks exactly like
      one that works.

    This is a cross-encoder improvised from a chat model: the model reads the query
    and each passage TOGETHER, which is what makes it more accurate than comparing
    two separately computed embeddings, and what makes it far too slow and costly to
    run over a whole corpus. So: retrieve wide (~50), rerank narrow (~5).
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str | None = None,
        max_chars: int = 500,
        max_tokens: int = 512,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    def prompt(self, query: str, candidates: Sequence[tuple[str, str]]) -> str:
        """Fill RERANK_PROMPT.

        `passages` is one block per candidate, separated by a blank line:

            [0] first passage text
            <blank line>
            [1] second passage text

        Number by POSITION (0, 1, 2 ...), not by doc_id: short numbers are cheaper
        and models copy them back reliably; long ids get mangled.

        Collapse each text's whitespace to single spaces (" ".join(text.split()))
        and then cut it to `self.max_chars` characters. Fifty full documents would
        blow your context budget and your bill.
        """
        # TODO: implement
        raise NotImplementedError

    def parse(self, raw: str | None, n: int) -> dict[int, float] | None:
        """Turn the model's reply into {index: score}, or None if nothing is usable.

        Spec:
          1. obj = parse_json(raw). Not a dict -> None
          2. scores = obj["scores"] if that key exists, else obj itself (models
             often drop the wrapper). Not a dict -> None
          3. for each key, value:
               * index = int(key) — also accept "[3]" (strip whitespace and
                 brackets); unparseable -> skip this entry
               * score = float(value); unparseable, a bool, or not finite (nan,
                 inf) -> skip
               * index outside 0..n-1 -> skip (the model invented a passage)
               * clamp score to [0, 10]
          4. no valid entries -> None
        """
        # TODO: implement
        raise NotImplementedError

    def rerank(
        self,
        query: str,
        candidates: Sequence[tuple[str, str]],
        top_n: int | None = 5,
    ) -> list[RerankResult]:
        """Reorder (doc_id, text) candidates by the model's scores. FAILS OPEN.

        Spec:
          * top_n=None means return all; a negative top_n means 0
          * 0 or 1 candidates -> return them as RerankResult(score=None) WITHOUT
            calling the model (there is nothing to reorder, so don't pay for it)
          * otherwise ONE call: prompt -> client.chat (temperature 0.0,
            max_tokens=self.max_tokens, model= only if set) -> parse
          * if the call raises (anything) OR parse returns None: increment
            `self.fallbacks` and treat every candidate as unscored
          * sort: scored candidates first, highest score first; then unscored ones;
            ties and unscored keep their original order
          * return the first top_n

        Fail open means: worst case you get back exactly the order you came in
        with. Never worse than not reranking, and never an exception.
        """
        # TODO: implement
        raise NotImplementedError


# ======================================================= query transformation


EXPAND_PROMPT = """\
Write {n} different search queries that would find documents answering the question
below. Use different wording and synonyms; keep each one short. Do not answer it.

QUESTION: {query}

Return ONLY a JSON array of {n} strings."""


def expand_query(client: Any, query: str, n: int = 3, *, model: str | None = None) -> list[str]:
    """Multi-query expansion: [the original query] + up to n rephrasings.

    Spec:
      * n <= 0 -> [query], without calling the model
      * one call with EXPAND_PROMPT (temperature 0.0, max_tokens=300)
      * parse with parse_json. Accept a JSON list, or a dict with a "queries" list.
        Anything else, or an exception from the client -> [query]
      * the ORIGINAL QUERY IS ALWAYS FIRST. The rephrasings are extra recall, not
        a replacement — a bad rewrite must never lose what the user actually typed
      * clean each item: skip non-strings, collapse whitespace to single spaces;
        skip empties and duplicates, where "duplicate" ignores case and whitespace
        and includes repeating the original query
      * keep at most n rephrasings

    Why it helps: users phrase things one way and documents another. Three phrasings
    searched separately and then fused find documents that any one of them misses.
    The price is n extra searches and one model call on every query.
    """
    # TODO: implement
    raise NotImplementedError


def multi_query_retrieve(
    queries: Sequence[str],
    retrieve_fn: Callable[[str, int], Sequence[Any]],
    k: int = 5,
    *,
    per_query: int | None = None,
    rrf_k: int = 60,
) -> list[str]:
    """Search with every query, fuse the rankings, return the top k doc ids.

    Spec:
      * k <= 0 or no queries -> []
      * per_query defaults to max(2 * k, 10): fetch more than k from each search,
        or fusion has nothing to choose between
      * call retrieve_fn(query, per_query) once per query; each result is a ranking
        in any form `reciprocal_rank_fusion` accepts
      * fuse with reciprocal_rank_fusion(rankings, k=rrf_k) and return the first k ids

    This is the same fusion as Exercise 3 — RRF does not care whether the lists
    came from two retrievers or from one retriever and three phrasings.
    """
    # TODO: implement
    raise NotImplementedError


REWRITE_PROMPT = """\
Rewrite the user's latest message as a single standalone search query. Resolve every
pronoun and reference ("it", "that one", "the second one") using the conversation.
Do not answer it. If it is already standalone, return it unchanged.

CONVERSATION:
{history}

LATEST MESSAGE: {question}

Return ONLY the rewritten query, on one line."""

#: Labels models like to put in front of the answer despite being told not to.
LABEL = re.compile(
    r"^(standalone (search )?(query|question)|rewritten( query)?|query)\s*:\s*",
    re.IGNORECASE,
)


def rewrite_followup(
    client: Any,
    history: Sequence[dict[str, Any]],
    question: str,
    *,
    max_turns: int = 6,
    max_chars: int = 500,
    model: str | None = None,
) -> str:
    """Conversational query rewriting: make a follow-up searchable on its own.

        history:  user: compare the Starter and Pro plans
                  assistant: Starter is $10/month, Pro is $30/month with SSO...
        question: what about the second one's limits?
        rewrite:  Pro plan usage limits

    Embed "what about the second one's limits?" and you get a vector for "limits"
    in general. The rewrite is what actually retrieves.

    Spec:
      * keep only messages whose role is "user" or "assistant" and whose content is
        a non-empty string (skip system prompts, tool results, None content)
      * keep the LAST max_turns of those (max_turns <= 0 keeps none)
      * none left -> return `question` unchanged WITHOUT calling the model. A first
        message has nothing to resolve
      * format them one per line as "role: content" (content stripped) into
        REWRITE_PROMPT; one call (temperature 0.0, max_tokens=200)
      * clean the reply:
          - take the first non-empty line, stripped
          - remove a leading label matching LABEL ("Standalone query: ...")
          - remove one pair of matching surrounding quotes: " ' or `
      * fall back to `question` if: the client raises, the reply is empty after
        cleaning, or it is longer than max_chars (the model answered the question
        instead of rewriting it)
    """
    # TODO: implement
    raise NotImplementedError
