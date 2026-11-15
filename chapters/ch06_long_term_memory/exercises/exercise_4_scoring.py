"""EXERCISE 4 — Ranking memories.

    pytest chapters/ch06_long_term_memory/tests -q -k scoring
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryKind(str, Enum):
    """SEMANTIC, EPISODIC, PROCEDURAL — values are the lowercase names."""

    SEMANTIC = "semantic"
    # TODO: add the other two


@dataclass
class Memory:
    """One remembered thing.

    Fields:
        text: str
        kind: MemoryKind = MemoryKind.SEMANTIC
        id: str = uuid4().hex
        subject: str = "default"        whose memory: a user id, project, team
        created_at: float = now
        last_used_at: float = now
        use_count: int = 0
        importance: float = 0.5         0-1, assigned at write time
        source: str = ""
    """

    text: str

    def to_metadata(self) -> dict[str, Any]:
        """Everything except `text`, as a flat dict for the vector store's metadata.
        Store `kind` as its `.value` so it survives JSON."""
        # TODO: implement
        raise NotImplementedError

    @classmethod
    def from_document(cls, document: Any) -> "Memory":
        """Rebuild a Memory from a `Document` (`.text` + `.metadata`).

        Be tolerant: missing keys get the defaults, and an unrecognised `kind` falls
        back to SEMANTIC rather than raising. Stored data outlives your code.
        """
        # TODO: implement
        raise NotImplementedError


DEFAULT_HALF_LIFE_S = 7 * 24 * 3600


def recency_weight(age_s: float, half_life_s: float = DEFAULT_HALF_LIFE_S) -> float:
    """Exponential decay in (0, 1].

    Spec:
      * age <= 0            -> 1.0
      * otherwise           -> 0.5 ** (age_s / half_life_s)

    So: brand new = 1.0, one half-life old = 0.5, two half-lives = 0.25.

    Exponential rather than linear because it never reaches zero — a very old memory
    becomes unlikely to surface, not impossible. Linear decay with a cutoff makes
    memories vanish abruptly on an arbitrary day.
    """
    # TODO: implement
    raise NotImplementedError


def composite_score(
    similarity: float,
    memory: Memory,
    *,
    now: float | None = None,
    half_life_s: float = DEFAULT_HALF_LIFE_S,
    w_similarity: float = 0.6,
    w_recency: float = 0.2,
    w_importance: float = 0.2,
) -> float:
    """Blend relevance, freshness and importance.

    Spec:
        recency = recency_weight(now - memory.created_at, half_life_s)
                  IF memory.kind is EPISODIC
                  else 1.0
        return w_similarity*similarity + w_recency*recency + w_importance*importance

    `now` defaults to time.time().

    WHY ONLY EPISODIC DECAYS: a fact about someone's job is not less true for being
    three months old, and a procedural rule ("run migrations first") does not expire.
    Decaying them would actively make retrieval worse. Only "things that happened"
    lose relevance with age.

    WHY DECAY AT ALL: given
        "favourite colour is blue"          similarity 0.82  (3 months old)
        "changed their mind, it's green"    similarity 0.79  (yesterday)
    pure similarity returns the stale one first. Recency breaks the tie correctly.
    """
    # TODO: implement
    raise NotImplementedError
