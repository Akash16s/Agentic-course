"""SOLUTION — Chapter 6b, Exercise 1."""

from __future__ import annotations

import math
from typing import Callable, Iterable

from agentlib.embeddings import tokenise


class BM25Index:
    """Okapi BM25 over an in-memory inverted index.

        score(D, Q) = sum over terms t in Q of
                      IDF(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |D| / avgdl))

        IDF(t)      = ln(1 + (N - n + 0.5) / (n + 0.5))

    tf     how often t appears in D
    |D|    D's length in tokens; avgdl the average length over the index
    N      documents in the index; n documents containing t

    k1 (default 1.5) controls tf SATURATION: the 1st mention of a term matters a lot,
    the 10th barely at all. b (default 0.75) controls LENGTH NORMALISATION: a long
    document mentions everything a few times by accident, so its tf counts for less.

    The "1 +" inside the log is the smoothed IDF used by Lucene/Elasticsearch. The
    original formula goes NEGATIVE for a term in more than half the documents, which
    means matching a common word would make a document rank lower than not matching
    it at all.

    >>> index = BM25Index()
    >>> index.add("a", "error E4012 means the card was declined")
    >>> index.add("b", "how to handle payment errors gracefully")
    >>> index.search("E4012")[0][0]
    'a'
    """

    def __init__(
        self,
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Callable[[str], list[str]] = tokenise,
    ) -> None:
        if k1 < 0:
            raise ValueError(f"k1 must be >= 0, got {k1}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b must be in [0, 1], got {b}")
        self.k1 = k1
        self.b = b
        self.tokenizer = tokenizer
        self._texts: dict[str, str] = {}
        self._tf: dict[str, dict[str, int]] = {}      # doc_id -> term -> count
        self._lengths: dict[str, int] = {}             # doc_id -> token count
        self._df: dict[str, int] = {}                  # term -> docs containing it
        self._total_length = 0

    # ------------------------------------------------------------- writing

    def add(self, doc_id: str, text: str) -> None:
        """Index one document. Re-adding an existing id replaces it."""
        if doc_id in self._texts:
            self.remove(doc_id)
        tokens = self.tokenizer(text)
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        self._texts[doc_id] = text
        self._tf[doc_id] = counts
        self._lengths[doc_id] = len(tokens)
        self._total_length += len(tokens)
        for term in counts:
            self._df[term] = self._df.get(term, 0) + 1

    def add_many(self, items: Iterable[tuple[str, str]]) -> None:
        for doc_id, text in items:
            self.add(doc_id, text)

    def remove(self, doc_id: str) -> bool:
        if doc_id not in self._texts:
            return False
        for term in self._tf[doc_id]:
            self._df[term] -= 1
            if self._df[term] == 0:
                del self._df[term]
        self._total_length -= self._lengths[doc_id]
        del self._texts[doc_id], self._tf[doc_id], self._lengths[doc_id]
        return True

    # ------------------------------------------------------------- reading

    def __len__(self) -> int:
        return len(self._texts)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self._texts

    def get(self, doc_id: str) -> str | None:
        return self._texts.get(doc_id)

    @property
    def avgdl(self) -> float:
        """Average document length in tokens. 0.0 for an empty index."""
        return self._total_length / len(self._texts) if self._texts else 0.0

    def idf(self, term: str) -> float:
        """Smoothed IDF. Never negative; 0.0 for a term no document contains."""
        n = self._df.get(term, 0)
        if n == 0:
            return 0.0
        N = len(self._texts)
        return math.log(1.0 + (N - n + 0.5) / (n + 0.5))

    def score(self, query: str, doc_id: str) -> float:
        """BM25 score of one document. Duplicate query terms count once."""
        counts = self._tf.get(doc_id)
        if counts is None:
            return 0.0
        avgdl = self.avgdl or 1.0  # every doc empty: avoid dividing by zero
        length_ratio = self._lengths[doc_id] / avgdl
        total = 0.0
        for term in set(self.tokenizer(query)):
            tf = counts.get(term, 0)
            if tf == 0:
                continue
            norm = tf + self.k1 * (1.0 - self.b + self.b * length_ratio)
            total += self.idf(term) * tf * (self.k1 + 1.0) / norm
        return total

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        """Top-k (doc_id, score), best first.

        Only documents matching at least one query term are returned — unlike vector
        search, BM25 is allowed to say "nothing matched". Ties keep insertion order.
        """
        if k <= 0 or not self._texts:
            return []
        terms = set(self.tokenizer(query))
        # only score documents that contain at least one query term
        candidates = [d for d in self._texts if any(t in self._tf[d] for t in terms)]
        scored = [(d, self.score(query, d)) for d in candidates]
        scored = [(d, s) for d, s in scored if s > 0.0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]
