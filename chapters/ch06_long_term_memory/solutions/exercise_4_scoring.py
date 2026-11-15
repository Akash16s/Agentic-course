"""SOLUTION — Chapter 6, Exercise 4."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryKind(str, Enum):
    """The three kinds worth distinguishing, borrowed from cognitive psychology
    because the categories turn out to be operationally useful.

    SEMANTIC   — timeless facts.      "Akash works in fintech."
    EPISODIC   — things that happened. "On 2026-09-14 we chose Postgres over MySQL."
    PROCEDURAL — how to do things.     "When deploying, always run migrations first."

    Why bother: they have different lifetimes and different retrieval rules. Semantic
    facts get UPDATED (the user changes jobs). Episodic memories accumulate and decay
    with age. Procedural memories should be retrieved by task, not by recency. One
    undifferentiated pile makes all three behave wrongly.
    """

    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


@dataclass
class Memory:
    """One remembered thing."""

    text: str
    kind: MemoryKind = MemoryKind.SEMANTIC
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    subject: str = "default"          # whose memory: a user id, a project, a team
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    use_count: int = 0
    importance: float = 0.5           # 0-1, set at write time
    source: str = ""                  # session id, document, "user said"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "subject": self.subject,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "importance": self.importance,
            "source": self.source,
        }

    @classmethod
    def from_document(cls, document: "Any") -> "Memory":
        m = document.metadata
        try:
            kind = MemoryKind(m.get("kind", "semantic"))
        except ValueError:
            # stored data outlives your code: an unknown kind from an older or newer
            # version must degrade, not crash the whole recall
            kind = MemoryKind.SEMANTIC
        return cls(
            text=document.text,
            kind=kind,
            id=document.id,
            subject=m.get("subject", "default"),
            created_at=m.get("created_at", 0.0),
            last_used_at=m.get("last_used_at", 0.0),
            use_count=int(m.get("use_count", 0)),
            importance=float(m.get("importance", 0.5)),
            source=m.get("source", ""),
        )


# --------------------------------------------------------------------- scoring

#: How fast episodic memories fade. 7 days to half weight.
DEFAULT_HALF_LIFE_S = 7 * 24 * 3600


def recency_weight(age_s: float, half_life_s: float = DEFAULT_HALF_LIFE_S) -> float:
    """Exponential decay in [0, 1]. 1.0 when brand new, 0.5 at one half-life."""
    if age_s <= 0:
        return 1.0
    return 0.5 ** (age_s / half_life_s)


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
    """Blend relevance, freshness and importance into one ranking number.

    Pure similarity is the wrong ranking for memory. "The user's favourite colour is
    blue" and "the user changed their mind, it's green now" are equally similar to
    "what colour do they like?" — recency is what breaks the tie.

    Semantic and procedural memories do NOT decay: a fact about someone's job is not
    less true for being three months old. Only episodic memories get the recency term.
    """
    now = now if now is not None else time.time()
    if memory.kind is MemoryKind.EPISODIC:
        recency = recency_weight(now - memory.created_at, half_life_s)
    else:
        recency = 1.0
    return (
        w_similarity * similarity
        + w_recency * recency
        + w_importance * memory.importance
    )
