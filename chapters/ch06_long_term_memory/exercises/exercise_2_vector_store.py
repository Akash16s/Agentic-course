"""EXERCISE 2 — The vector store.

    pytest chapters/ch06_long_term_memory/tests -q -k vector_store
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .exercise_1_similarity import Embedder, cosine_similarity


@dataclass
class Document:
    """One stored item.

    Fields: id: str, text: str, embedding: list[float] = [], metadata: dict = {}
    """

    id: str
    text: str


@dataclass
class SearchResult:
    """A document plus its score. Expose `.text` and `.metadata` as properties so
    callers rarely need to reach through `.document`."""

    document: Document
    score: float

    @property
    def text(self) -> str:
        # TODO: implement
        raise NotImplementedError

    @property
    def metadata(self) -> dict[str, Any]:
        # TODO: implement
        raise NotImplementedError


class VectorStore:
    """Brute-force cosine search over an in-memory dict.

    O(n) per query. Fine to ~50k vectors; past that you want an approximate index
    (HNSW/IVF) in pgvector, Qdrant or LanceDB — which expose this same interface.
    """

    def __init__(self, embedder: Embedder) -> None:
        """Keep `self.embedder`, `self._docs: dict[str, Document]`, a threading.Lock."""
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------- writing

    def add(self, text: str, *, doc_id: str | None = None,
            metadata: dict[str, Any] | None = None) -> Document:
        """One document. Implement it by delegating to add_many so there is one
        code path, not two that drift apart."""
        # TODO: implement
        raise NotImplementedError

    def add_many(
        self,
        texts: list[str],
        *,
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str | None] | None = None,
    ) -> list[Document]:
        """Embed and store several texts using ONE `embed_batch` call.

        Spec:
          * [] -> []
          * missing metadatas/ids default to {} / None per text
          * a None id becomes `uuid.uuid4().hex`
          * COPY the metadata dict (the caller may mutate theirs)
          * return the created Documents, in order

        The single `embed_batch` call is the point. Looping over `add` would make 100
        API round trips where one would do.
        """
        # TODO: implement
        raise NotImplementedError

    def delete(self, doc_id: str) -> bool:
        """Return True if something was removed, False if it wasn't there."""
        # TODO: implement
        raise NotImplementedError

    def clear(self) -> None:
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------- reading

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

    def __contains__(self, doc_id: object) -> bool:
        # TODO: implement
        raise NotImplementedError

    def get(self, doc_id: str) -> Document | None:
        # TODO: implement
        raise NotImplementedError

    @property
    def documents(self) -> list[Document]:
        # TODO: implement
        raise NotImplementedError

    def search(self, query: str, *, k: int = 5, min_score: float = 0.0,
               where: Callable[[Document], bool] | None = None) -> list[SearchResult]:
        """Embed the query, then delegate to `search_by_vector`."""
        # TODO: implement
        raise NotImplementedError

    def search_by_vector(
        self,
        vector: list[float],
        *,
        k: int = 5,
        min_score: float = 0.0,
        where: Callable[[Document], bool] | None = None,
    ) -> list[SearchResult]:
        """Top-k by cosine similarity, highest first.

        Spec, in this order:
          1. filter by `where` FIRST (cheaper than scoring, and it is a filter not a
             re-rank — a filtered-out document must never appear)
          2. score every survivor
          3. drop anything below `min_score`
          4. sort descending, return the first k

        `min_score` is the argument people forget. Without it, the nearest neighbour
        of any query is still SOMETHING, so an unrelated question returns k
        confidently irrelevant documents which the model then cites.
        """
        # TODO: implement
        raise NotImplementedError

    # --------------------------------------------------------- persistence

    def save(self, path: str) -> None:
        """Write the documents as a JSON list (use `dataclasses.asdict`)."""
        # TODO: implement
        raise NotImplementedError

    def load(self, path: str) -> None:
        """Replace the contents from a file written by `save`.

        Not checked here, but essential in production: that the file was written with
        the SAME embedding model. Mixing models gives valid numbers and meaningless
        similarities — no error, just silently wrong retrieval.
        """
        # TODO: implement
        raise NotImplementedError
