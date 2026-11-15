"""EXERCISE 1 — Vectors and similarity.

    pytest chapters/ch06_long_term_memory/tests -q -k similarity
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

Vector = list[float]

_WORD = re.compile(r"[a-z0-9']+")

STOPWORDS = frozenset("""
a an and are as at be been by for from had has have he her his i if in into is it its
of on or she that the their them there these they this to was were what when where
which who will with would you your
""".split())


def tokenise(text: str, *, drop_stopwords: bool = True) -> list[str]:
    """Lowercase, split on word characters, optionally drop stopwords.

    Spec:
      * use `_WORD.findall(text.lower())`
      * if drop_stopwords: remove STOPWORDS — BUT if that leaves nothing (a query
        like "what is it"), return the original words instead. An empty vector
        matches nothing, which is a worse answer than a weak match.

    Why drop them at all: without it, "the dog ran in the park" and "the cat sat on
    the mat" score ~0.5 similar purely on "the/in/on/a". That is worse than useless.
    """
    # TODO: implement
    raise NotImplementedError


def l2_normalise(vector: Vector) -> Vector:
    """Scale a vector to length 1.

    Spec: divide every component by sqrt(sum of squares). A ZERO vector is returned
    unchanged (a copy) — do not divide by zero.

    Why: once every stored vector is unit length, cosine similarity becomes a plain
    dot product. No square roots at query time. Every real vector DB does this.
    """
    # TODO: implement
    raise NotImplementedError


def dot(a: Vector, b: Vector) -> float:
    """Sum of element-wise products."""
    # TODO: implement
    raise NotImplementedError


def cosine_similarity(a: Vector, b: Vector) -> float:
    """Cosine of the angle between two vectors.

    Spec:
      * different lengths -> raise ValueError (a dimension mismatch is a bug in your
        pipeline — usually two different embedding models — and must be loud)
      * either vector all-zero -> return 0.0, do NOT raise. An empty document is not
        an error; it is simply similar to nothing.
      * otherwise dot(a,b) / (|a| * |b|)

    >>> cosine_similarity([1, 0], [1, 0])
    1.0
    >>> cosine_similarity([1, 0], [0, 1])
    0.0
    """
    # TODO: implement
    raise NotImplementedError


class Embedder(ABC):
    """Text in, vector out."""

    dimensions: int = 0

    @abstractmethod
    def embed(self, text: str) -> Vector: ...

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Default: one at a time. Real backends override this — one request for 100
        texts is far cheaper and faster than 100 requests."""
        return [self.embed(t) for t in texts]


class HashingEmbedder(Embedder):
    """Bag-of-words via the hashing trick. Free, offline, deterministic.

    __init__(self, dimensions: int = 1024, *, bigrams: bool = True)

    embed(text):
      1. start with a zero vector of `dimensions`
      2. words = tokenise(text)
      3. for each word: vector[bucket(word)] += 1.0
      4. if self.bigrams: for each adjacent pair (a, b):
             vector[bucket(f"{a}_{b}")] += 0.5
         (bigrams give word order some weight — without them "dog bites man" and
          "man bites dog" are identical vectors)
      5. return l2_normalise(vector)

    bucket(token):
        blake2b(token.encode(), digest_size=8) -> int -> % dimensions
        Use blake2b, not Python's `hash()`: `hash()` is randomised per process, so
        your stored vectors would stop matching after a restart.

    WHY 1024 AND NOT 256: at 256 dimensions unrelated words collide often enough that
    a document sharing no words with the query can outrank one that does. Run
    examples/02_collisions.py to see it.
    """

    def __init__(self, dimensions: int = 1024, *, bigrams: bool = True) -> None:
        # TODO: implement
        raise NotImplementedError

    def _bucket(self, token: str) -> int:
        # TODO: implement
        raise NotImplementedError

    def embed(self, text: str) -> Vector:
        # TODO: implement
        raise NotImplementedError


class CachedEmbedder(Embedder):
    """Memoise by exact text.

    __init__(self, inner: Embedder, *, max_size: int = 10_000)

    Track `self.hits` and `self.misses` so the cache can be proven to work.
    On overflow evict the oldest entry (dicts preserve insertion order, so
    `self._cache.pop(next(iter(self._cache)))` is a one-line FIFO).

    Override `embed_batch` too: collect the texts NOT in the cache, embed those in one
    call, then assemble the results in the original order. Doing it one-at-a-time
    through `embed` throws away the batching win.
    """

    def __init__(self, inner: Embedder, *, max_size: int = 10_000) -> None:
        # TODO: implement
        raise NotImplementedError

    def embed(self, text: str) -> Vector:
        # TODO: implement
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        # TODO: implement
        raise NotImplementedError
