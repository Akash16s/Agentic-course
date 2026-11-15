"""EXERCISE 5 — The memory store.

    pytest chapters/ch06_long_term_memory/tests -q -k memory_store
"""

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
    """Long-term memory over a VectorStore, with write policies and ranking."""

    def __init__(
        self,
        embedder: Embedder,
        *,
        dedup_threshold: float = 0.95,
        half_life_s: float = DEFAULT_HALF_LIFE_S,
    ) -> None:
        """Build `self.vectors = VectorStore(embedder)` and keep the two settings."""
        # TODO: implement
        raise NotImplementedError

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

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
        """Store a memory unless we already know it. Returns the Memory, or None.

        Spec:
          1. strip the text; empty -> return None
          2. search the store for it, LIMITED TO THE SAME SUBJECT, k=1
          3. if a hit scores >= self.dedup_threshold -> return None (already known)
          4. build a Memory (created_at = `now` or time.time(); last_used_at = same)
          5. `self.vectors.add(text, doc_id=memory.id, metadata=memory.to_metadata())`
          6. return it

        DEDUP IS A CORRECTNESS FEATURE, not an optimisation. An agent that writes
        memories every turn accumulates forty copies of "the user is called Akash",
        and since `k` is finite, recall then returns that one fact forty times and
        crowds out everything else. The store gets bigger and recall gets worse.

        Scoping dedup to the subject matters too: two different users may legitimately
        have the same fact.
        """
        # TODO: implement
        raise NotImplementedError

    def forget(self, memory_id: str) -> bool:
        # TODO: implement
        raise NotImplementedError

    def update(self, memory_id: str, text: str) -> Memory | None:
        """Replace a memory's TEXT, keeping its id and metadata. None if not found.

        Delete then re-add with the same id and the old metadata — the text changed,
        so the embedding must be recomputed.

        This is how semantic facts change. "Akash works at Kryptos" must REPLACE
        "Akash works at Acme". Keeping both means recall returns both and the model
        picks one at random.
        """
        # TODO: implement
        raise NotImplementedError

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
        """Retrieve memories ranked by `composite_score`.

        Spec:
          1. build a `where` predicate: same `subject`, and if `kinds` was given, the
             document's kind must be one of them
          2. OVER-FETCH: `self.vectors.search(query, k=max(k*3, 10),
             min_score=min_similarity, where=...)`
          3. rebuild each Memory, compute its composite score, sort descending
          4. take the first k
          5. if `touch`, bump `use_count` and `last_used_at` on each returned memory
          6. return the Memories

        WHY OVER-FETCH: the composite score can promote a memory that similarity alone
        did not rank in the top k. If you only re-rank what similarity already picked,
        the recency and importance weights can never change the outcome — they become
        decorative.
        """
        # TODO: implement
        raise NotImplementedError

    def all_memories(self, subject: str | None = None) -> list[Memory]:
        """Everything, optionally filtered by subject. For inspection and tests."""
        # TODO: implement
        raise NotImplementedError

    def _touch(self, memory: Memory, now: float) -> None:
        """Bump use_count and last_used_at on the STORED document.

        Mutating the returned `Memory` object would do nothing — it is a copy. Reach
        into `self.vectors.get(memory.id).metadata`.

        Why track it: usage is the best signal for what to keep when you eventually
        need to forget things. A memory retrieved fifty times is load-bearing; one
        never retrieved in 90 days is dead weight.
        """
        # TODO: implement
        raise NotImplementedError

    # ---------------------------------------------------------- formatting

    def as_context(self, memories: list[Memory], *, header: str = "What you know") -> str:
        """Render for a system prompt. Empty list -> "".

        Format:
            What you know:
            - (semantic) Akash prefers Python over JavaScript
            - (episodic) We chose Postgres on 2026-09-14

        Label the kind: the model should weigh "we decided X on Tuesday" differently
        from "the user prefers Y".
        """
        # TODO: implement
        raise NotImplementedError
