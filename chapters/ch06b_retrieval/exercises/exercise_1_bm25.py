"""EXERCISE 1 — BM25, the keyword search inside every search engine.

    pytest chapters/ch06b_retrieval/tests -q -k bm25
"""

from __future__ import annotations

import math
from typing import Callable, Iterable

from agentlib.embeddings import tokenise


class BM25Index:
    """Okapi BM25 over an in-memory inverted index.

        score(D, Q) = sum over the DISTINCT terms t in Q of
                      IDF(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |D| / avgdl))

        IDF(t)      = ln(1 + (N - n + 0.5) / (n + 0.5))

    tf     how many times t appears in D
    |D|    D's length in tokens (after `tokenise`, so stopwords are not counted)
    avgdl  the average |D| over the whole index
    N      documents in the index
    n      documents that contain t

    k1 — tf SATURATION. The first "refund" in a document says a lot; the tenth says
         almost nothing new. With k1=1.5 the tf part goes 1.0, 1.43, 1.67, 1.92 for
         tf = 1, 2, 3, 5 and can never exceed k1 + 1 = 2.5.
    b  — LENGTH NORMALISATION. A long document mentions everything a few times by
         accident. b=0.75 discounts tf in longer-than-average documents; b=0 turns
         it off; b=1 applies it fully.

    The "1 +" inside the log is the smoothed IDF Lucene and Elasticsearch use. The
    original form, ln((N - n + 0.5) / (n + 0.5)), goes NEGATIVE once a term is in
    more than half the documents — so matching a common word would push a document
    BELOW one that did not match at all.

    __init__(self, *, k1=1.5, b=0.75, tokenizer=tokenise)
      * k1 < 0          -> ValueError
      * b outside [0,1] -> ValueError
      * store all three as attributes of the same name

    What to keep (suggested — the tests only use the public methods):
        self._texts   dict[doc_id, original text]
        self._tf      dict[doc_id, dict[term, count]]
        self._lengths dict[doc_id, token count]
        self._df      dict[term, number of docs containing it]
        a running total of all lengths, so avgdl is O(1)
    """

    def __init__(
        self,
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Callable[[str], list[str]] = tokenise,
    ) -> None:
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------- writing

    def add(self, doc_id: str, text: str) -> None:
        """Index one document.

        Spec:
          * tokenise with `self.tokenizer`, count each term
          * update document frequency: +1 per DISTINCT term, not per occurrence
          * re-adding an existing doc_id REPLACES it (call `remove` first), so the
            document counts and frequencies stay right
          * an empty text is allowed: it has length 0 and matches nothing
        """
        # TODO: implement
        raise NotImplementedError

    def add_many(self, items: Iterable[tuple[str, str]]) -> None:
        """`add` each (doc_id, text) pair."""
        # TODO: implement
        raise NotImplementedError

    def remove(self, doc_id: str) -> bool:
        """Undo `add`. True if something was removed, False if it wasn't there.

        Decrement every one of its terms' document frequency (and delete a term
        whose frequency reaches 0), and take its length off the running total.
        """
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------- reading

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

    def __contains__(self, doc_id: object) -> bool:
        # TODO: implement
        raise NotImplementedError

    def get(self, doc_id: str) -> str | None:
        """The original text, or None."""
        # TODO: implement
        raise NotImplementedError

    @property
    def avgdl(self) -> float:
        """Average document length in tokens. 0.0 for an empty index."""
        # TODO: implement
        raise NotImplementedError

    def idf(self, term: str) -> float:
        """Smoothed IDF: ln(1 + (N - n + 0.5) / (n + 0.5)).

        Spec:
          * a term no document contains -> 0.0 (it cannot help any document)
          * otherwise always > 0, however common the term
          * rarer terms get a higher IDF
        """
        # TODO: implement
        raise NotImplementedError

    def score(self, query: str, doc_id: str) -> float:
        """The BM25 score of one document for one query.

        Spec:
          * unknown doc_id -> 0.0
          * tokenise the query and use each DISTINCT term once
            ("refund refund refund" scores the same as "refund")
          * skip terms the document does not contain (tf = 0 adds nothing)
          * if avgdl is 0 (every document is empty) use 1.0 to avoid dividing by 0
        """
        # TODO: implement
        raise NotImplementedError

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        """Top-k (doc_id, score) pairs, best first.

        Spec:
          * k <= 0 or an empty index -> []
          * only documents with score > 0 are returned. Unlike vector search,
            BM25 can honestly say "nothing matched" — a query of only unknown words
            returns []
          * sort by score, descending; ties keep insertion order (Python's sort is
            stable, so this is free if you score documents in insertion order)

        Efficiency hint: only score documents that contain at least one query term.
        A real engine walks the inverted index (term -> docs) instead of scanning
        every document; for this exercise either is fine.
        """
        # TODO: implement
        raise NotImplementedError
