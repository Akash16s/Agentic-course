"""Long-term memory — what the agent knows about a user, across conversations.

Promoted from Chapter 6.

Short-term memory (Chapter 5) is about a CONVERSATION. This is about a USER, or a
domain, or a project: facts that should outlive the thread they were mentioned in.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from agentlib.embeddings import Embedder
from agentlib.memory.vector import Document, SearchResult, VectorStore


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


# ----------------------------------------------------------------------- store


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


# ------------------------------------------------------------ fact extraction

EXTRACTION_PROMPT = """\
Extract durable facts worth remembering about the user from this conversation.

Return a JSON array. Each item: {{"text": "...", "kind": "semantic|episodic|procedural", \
"importance": 0.0-1.0}}

  semantic   = a timeless fact about the user or their world
  episodic   = something that happened, with its date if known
  procedural = a rule or preference about HOW to do things

Rules:
- Write each fact so it makes sense with NO other context. "He prefers it" is useless;
  "Akash prefers Python over JavaScript" is a memory.
- Only include things that will still matter next week. Skip pleasantries, skip the
  mechanics of this particular task.
- Prefer few good facts to many weak ones. An empty array is a valid answer.

CONVERSATION:
{transcript}

JSON array only, no commentary."""


def extract_memories(
    transcript: str,
    call_model: Callable[[str], str],
    *,
    subject: str = "default",
) -> list[Memory]:
    """Ask a model what is worth remembering. Never raises on bad output.

    Extraction is the part everyone underestimates. An agent that remembers
    everything is an agent whose recall is 90% noise, and noise crowds out signal
    because `k` is finite. The prompt above spends most of its words on what NOT to
    keep, deliberately.
    """
    raw = call_model(EXTRACTION_PROMPT.format(transcript=transcript))
    items = _parse_json_array(raw)

    memories: list[Memory] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        try:
            kind = MemoryKind(item.get("kind", "semantic"))
        except ValueError:
            kind = MemoryKind.SEMANTIC
        try:
            importance = min(1.0, max(0.0, float(item.get("importance", 0.5))))
        except (TypeError, ValueError):
            importance = 0.5
        memories.append(
            Memory(text=text, kind=kind, subject=subject, importance=importance)
        )
    return memories


def _parse_json_array(raw: str) -> list[Any]:
    """Pull a JSON array out of a model response that may be wrapped in prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1] if "```" in raw[3:] else raw[3:]
        raw = raw.removeprefix("json").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(raw[start: end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
