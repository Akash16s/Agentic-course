"""A vector store, from scratch.

Promoted from Chapter 6.

Pure Python, no numpy, no FAISS. It does a brute-force scan: compare the query to
every stored vector and keep the best. That is O(n) per query and it is completely
fine up to roughly 10,000-50,000 vectors — which covers a great many real agents.

Past that you want an approximate index (HNSW, IVF) and a real database: pgvector,
Qdrant, Chroma, LanceDB. The INTERFACE below is the same one they all expose, so
swapping is a day's work. Understanding what they do is why we build it first.
"""

from __future__ import annotations

import json
import math
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from agentlib.embeddings import Embedder, cosine_similarity


@dataclass
class Document:
    """One stored item."""

    id: str
    text: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    document: Document
    score: float

    @property
    def text(self) -> str:
        return self.document.text

    @property
    def metadata(self) -> dict[str, Any]:
        return self.document.metadata


class VectorStore:
    """Brute-force cosine search over an in-memory list.

    >>> store = VectorStore(HashingEmbedder())
    >>> store.add("Postgres is our primary database")
    >>> store.search("what database do we use?")[0].text
    'Postgres is our primary database'
    """

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._docs: dict[str, Document] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------- writing

    def add(
        self,
        text: str,
        *,
        doc_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        return self.add_many([text], metadatas=[metadata or {}], ids=[doc_id])[0]

    def add_many(
        self,
        texts: list[str],
        *,
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str | None] | None = None,
    ) -> list[Document]:
        """Embed and store several texts in ONE embedding call.

        Batching matters: 100 separate API calls is ~100x the latency and, with
        per-request overhead, meaningfully more money than one call with 100 inputs.
        """
        if not texts:
            return []
        metadatas = metadatas or [{} for _ in texts]
        ids = ids or [None for _ in texts]
        vectors = self.embedder.embed_batch(texts)

        created: list[Document] = []
        with self._lock:
            for text, vector, metadata, doc_id in zip(texts, vectors, metadatas, ids):
                document = Document(
                    id=doc_id or uuid.uuid4().hex,
                    text=text,
                    embedding=vector,
                    metadata=dict(metadata or {}),
                )
                self._docs[document.id] = document
                created.append(document)
        return created

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            return self._docs.pop(doc_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()

    # ------------------------------------------------------------- reading

    def __len__(self) -> int:
        return len(self._docs)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self._docs

    def get(self, doc_id: str) -> Document | None:
        return self._docs.get(doc_id)

    @property
    def documents(self) -> list[Document]:
        return list(self._docs.values())

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        min_score: float = 0.0,
        where: Callable[[Document], bool] | None = None,
    ) -> list[SearchResult]:
        """Top-k most similar documents.

        `min_score` is the argument people forget, and forgetting it is why RAG
        systems confidently cite irrelevant documents: with an empty-ish store, the
        nearest neighbour of ANY query is still *something*. A floor turns "here is
        the closest thing I have" into "I found nothing relevant", which is a far more
        useful answer.

        `where` filters BEFORE scoring, so it also saves work.
        """
        query_vector = self.embedder.embed(query)
        return self.search_by_vector(
            query_vector, k=k, min_score=min_score, where=where
        )

    def search_by_vector(
        self,
        vector: list[float],
        *,
        k: int = 5,
        min_score: float = 0.0,
        where: Callable[[Document], bool] | None = None,
    ) -> list[SearchResult]:
        candidates = [d for d in self._docs.values() if where is None or where(d)]
        scored = [
            SearchResult(d, cosine_similarity(vector, d.embedding)) for d in candidates
        ]
        scored = [r for r in scored if r.score >= min_score]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]

    # --------------------------------------------------------- persistence

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([asdict(d) for d in self._docs.values()], handle)

    def load(self, path: str) -> None:
        """Replace the contents from a file written by `save`.

        Note what is NOT checked here and should be in production: that the file was
        written with the SAME embedding model. Mixing vectors from two models gives
        you silent nonsense — the numbers are all valid, the similarities are
        meaningless. Store the model name alongside and refuse a mismatch.
        """
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        with self._lock:
            self._docs = {
                d["id"]: Document(
                    id=d["id"],
                    text=d["text"],
                    embedding=d["embedding"],
                    metadata=d.get("metadata", {}),
                )
                for d in raw
            }


# ------------------------------------------------------------------ chunking


def chunk_text(
    text: str,
    *,
    max_chars: int = 1_000,
    overlap: int = 150,
    separators: tuple[str, ...] = ("\n\n", "\n", ". ", " "),
) -> list[str]:
    """Split text into overlapping chunks, preferring natural boundaries.

    Two parameters, two reasons:

    `max_chars` — a chunk is the unit of retrieval. Too big and you retrieve a page
    to answer one sentence, diluting the context. Too small and you cut sentences in
    half and lose the meaning. 500-1500 characters is the usual sweet spot.

    `overlap` — a fact that straddles a boundary would otherwise be in neither chunk.
    Overlap means it is fully present in at least one. ~10-20% of max_chars.

    The separator list is a preference order: split on paragraphs if you can, then
    lines, then sentences, then words, and only hard-cut if a single "word" is longer
    than the chunk.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # Clamp the overlap to half the chunk. Without this, overlap >= max_chars makes
    # `start` advance by the +1 guard alone: 1,000 characters becomes ~900 chunks of
    # 100 characters each. It terminates, which is why the +1 is there, but it is
    # useless output and it looks like a hang.
    overlap = max(0, min(overlap, max_chars // 2))

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # walk the separators looking for a clean break near the end
            for separator in separators:
                cut = text.rfind(separator, start + max_chars // 2, end)
                if cut != -1:
                    end = cut + len(separator)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)  # the +1 guarantees progress
    return chunks
