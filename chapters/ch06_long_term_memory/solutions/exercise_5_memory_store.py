"""SOLUTION — Chapter 6, Exercise 5."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from .exercise_1_similarity import Embedder
from .exercise_2_vector_store import Document, VectorStore
from .exercise_4_scoring import (
    DEFAULT_HALF_LIFE_S,
    Memory,
    MemoryKind,
    composite_score,
)


class MemoryStore:
    """Long-term memory over a VectorStore, with write policies and decay.

    >>> store = MemoryStore(HashingEmbedder())
    >>> store.remember("Akash prefers Python", subject="akash")
    >>> store.recall("what language does he like?", subject="akash")[0].text
    'Akash prefers Python'
    """

    def __init__(
        self,
        embedder: Embedder,
        *,
        dedup_threshold: float = 0.95,
        half_life_s: float = DEFAULT_HALF_LIFE_S,
    ) -> None:
        self.vectors = VectorStore(embedder)
        self.dedup_threshold = dedup_threshold
        self.half_life_s = half_life_s

    def __len__(self) -> int:
        return len(self.vectors)

    # ----------------------------------------------------------- writing

    def remember(
        self,
        text: str,
        *,
        kind: MemoryKind = MemoryKind.SEMANTIC,
        subject: str = "default",
        importance: float = 0.5,
        source: str = "",
        now: float | None = None,
    ) -> Memory | None:
        """Store a memory, unless we already know it.

        Returns the stored Memory, or None if it was a near-duplicate.

        Deduplication is not an optimisation, it is a correctness feature. Without it
        an agent that writes memories every turn accumulates forty copies of "the user
        is called Akash", and then every recall returns the same fact forty times and
        crowds out everything else.
        """
        text = text.strip()
        if not text:
            return None

        existing = self.vectors.search(
            text, k=1, where=lambda d: d.metadata.get("subject") == subject
        )
        if existing and existing[0].score >= self.dedup_threshold:
            return None

        memory = Memory(
            text=text,
            kind=kind,
            subject=subject,
            importance=importance,
            source=source,
            created_at=now if now is not None else time.time(),
        )
        memory.last_used_at = memory.created_at
        self.vectors.add(text, doc_id=memory.id, metadata=memory.to_metadata())
        return memory

    def forget(self, memory_id: str) -> bool:
        return self.vectors.delete(memory_id)

    def update(self, memory_id: str, text: str) -> Memory | None:
        """Replace a memory's text, keeping its id and creation time.

        This is how semantic facts change. "Akash works at Kryptos" should REPLACE
        "Akash works at Acme", not sit next to it — otherwise recall returns both and
        the model has to guess which is current.
        """
        document = self.vectors.get(memory_id)
        if document is None:
            return None
        metadata = dict(document.metadata)
        self.vectors.delete(memory_id)
        self.vectors.add(text, doc_id=memory_id, metadata=metadata)
        return Memory.from_document(self.vectors.get(memory_id))

    # ----------------------------------------------------------- reading

    def recall(
        self,
        query: str,
        *,
        subject: str = "default",
        k: int = 5,
        kinds: list[MemoryKind] | None = None,
        min_similarity: float = 0.05,
        now: float | None = None,
        touch: bool = True,
    ) -> list[Memory]:
        """Retrieve memories, ranked by the composite score.

        Over-fetches from the vector store (3k) before re-ranking, because the
        composite score can promote a memory that was not in the raw top-k. Ranking
        only what similarity already picked would make the recency and importance
        terms nearly decorative.
        """
        wanted = {kind.value for kind in kinds} if kinds else None

        def matches(document: Document) -> bool:
            if document.metadata.get("subject") != subject:
                return False
            return wanted is None or document.metadata.get("kind") in wanted

        hits = self.vectors.search(
            query, k=max(k * 3, 10), min_score=min_similarity, where=matches
        )
        now = now if now is not None else time.time()
        scored = [
            (composite_score(hit.score, Memory.from_document(hit.document),
                             now=now, half_life_s=self.half_life_s),
             Memory.from_document(hit.document))
            for hit in hits
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        chosen = [memory for _, memory in scored[:k]]

        if touch:
            for memory in chosen:
                self._touch(memory, now)
        return chosen

    def all_memories(self, subject: str | None = None) -> list[Memory]:
        return [
            Memory.from_document(d)
            for d in self.vectors.documents
            if subject is None or d.metadata.get("subject") == subject
        ]

    def _touch(self, memory: Memory, now: float) -> None:
        """Record that a memory was used. Frequently-used memories are worth keeping."""
        document = self.vectors.get(memory.id)
        if document is None:
            return
        document.metadata["use_count"] = int(document.metadata.get("use_count", 0)) + 1
        document.metadata["last_used_at"] = now

    # ---------------------------------------------------------- formatting

    def as_context(self, memories: list[Memory], *, header: str = "What you know") -> str:
        """Render memories for a system prompt.

        Labelled by kind, because the model should treat "we decided X on Tuesday"
        differently from "the user prefers Y".
        """
        if not memories:
            return ""
        lines = [f"{header}:"]
        for memory in memories:
            lines.append(f"- ({memory.kind.value}) {memory.text}")
        return "\n".join(lines)
