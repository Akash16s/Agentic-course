"""SOLUTION — Chapter 6, Exercise 1."""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

Vector = list[float]

_WORD = re.compile(r"[a-z0-9']+")

#: Words that appear in everything and therefore distinguish nothing. Without this,
#: "the dog ran in the park" and "the cat sat on the mat" score ~0.5 similar purely
#: on "the", "in", "on", "a" — which is worse than useless for retrieval.
STOPWORDS = frozenset("""
a an and are as at be been by for from had has have he her his i if in into is it its
of on or she that the their them there these they this to was were what when where
which who will with would you your
""".split())


def tokenise(text: str, *, drop_stopwords: bool = True) -> list[str]:
    """Crude word split. Good enough for the hashing embedder."""
    words = _WORD.findall(text.lower())
    if drop_stopwords:
        kept = [w for w in words if w not in STOPWORDS]
        # if a query is ALL stopwords ("what is it"), keep them rather than
        # returning an empty vector that matches nothing
        return kept or words
    return words


def l2_normalise(vector: Vector) -> Vector:
    """Scale to unit length.

    Once every vector is unit length, cosine similarity is just a dot product — no
    division, no repeated magnitude computation. Real vector databases store
    normalised vectors for exactly this reason.
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return list(vector)
    return [x / norm for x in vector]

class Embedder(ABC):
    """Text in, vector out."""

    dimensions: int = 0

    @abstractmethod
    def embed(self, text: str) -> Vector: ...

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Override this when your backend supports batching — it usually does, and
        one request for 100 texts is far cheaper and faster than 100 requests."""
        return [self.embed(t) for t in texts]


class HashingEmbedder(Embedder):
    """A bag-of-words vector via the hashing trick. Free, offline, deterministic.

    How it works: hash each word to a bucket in [0, dimensions), add its weight there,
    then L2-normalise. Two texts sharing words land close together.

    What it CANNOT do: "car" and "automobile" hash to unrelated buckets, so it has no
    notion of meaning. That is the whole difference between lexical and semantic
    search, and feeling the limitation is more instructive than reading about it.

    Bigrams are included so word order carries a little weight — without them
    "dog bites man" and "man bites dog" are identical.

    WHY 1024 DIMENSIONS BY DEFAULT: with 256, unrelated words collide into the same
    bucket often enough to produce visible nonsense — a document sharing no words
    with the query can outrank one that does. Run
    `examples/02_collisions.py` to watch it happen. Real embedding models use
    384-3072 dimensions for the same reason, though theirs are learned rather than
    hashed.
    """

    def __init__(self, dimensions: int = 1024, *, bigrams: bool = True) -> None:
        self.dimensions = dimensions
        self.bigrams = bigrams

    def _bucket(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dimensions

    def embed(self, text: str) -> Vector:
        vector = [0.0] * self.dimensions
        words = tokenise(text)
        for word in words:
            vector[self._bucket(word)] += 1.0
        if self.bigrams:
            for a, b in zip(words, words[1:]):
                vector[self._bucket(f"{a}_{b}")] += 0.5
        return l2_normalise(vector)

class CachedEmbedder(Embedder):
    """Memoise by exact text.

    Embeddings are deterministic, so re-embedding the same string is pure waste — and
    it happens constantly: the same query retried, the same document re-indexed, the
    same system prompt fragment. A dict removes it.
    """

    def __init__(self, inner: Embedder, *, max_size: int = 10_000) -> None:
        self.inner = inner
        self.dimensions = inner.dimensions
        self.max_size = max_size
        self._cache: dict[str, Vector] = {}
        self.hits = 0
        self.misses = 0

    def embed(self, text: str) -> Vector:
        cached = self._cache.get(text)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        vector = self.inner.embed(text)
        if len(self._cache) >= self.max_size:
            self._cache.pop(next(iter(self._cache)))  # crude FIFO eviction
        self._cache[text] = vector
        return vector

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        missing = [t for t in texts if t not in self._cache]
        if missing:
            self.misses += len(missing)
            for text, vector in zip(missing, self.inner.embed_batch(missing)):
                self._cache[text] = vector
        self.hits += len(texts) - len(missing)
        return [self._cache[t] for t in texts]

def dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def cosine_similarity(a: Vector, b: Vector) -> float:
    """Cosine of the angle between two vectors, in [-1, 1].

    Why cosine and not Euclidean distance: cosine ignores magnitude and compares only
    direction. A two-sentence note and a two-page essay on the same topic point the
    same way but have very different lengths, and you want them to match.

    Returns 0.0 for a zero vector rather than raising — an empty document is not an
    error, it is just similar to nothing.
    """
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} != {len(b)}")
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)
