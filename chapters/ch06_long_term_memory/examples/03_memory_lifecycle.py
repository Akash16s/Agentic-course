"""Writing, deduplicating, ranking and updating memories. Free and offline.

    python chapters/ch06_long_term_memory/examples/03_memory_lifecycle.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.embeddings import HashingEmbedder
from agentlib.memory.long_term import (
    MemoryKind,
    MemoryStore,
    composite_score,
    recency_weight,
)

NOW = time.time()
DAY = 24 * 3600
store = MemoryStore(HashingEmbedder())

print("=" * 72)
print("1. WRITING (and refusing to write duplicates)")
print("=" * 72)
writes = [
    ("Akash works at Kryptos on crypto tax software", MemoryKind.SEMANTIC, 0.9, NOW),
    ("Akash prefers Python over JavaScript", MemoryKind.SEMANTIC, 0.7, NOW),
    ("Akash works at Kryptos on crypto tax software", MemoryKind.SEMANTIC, 0.9, NOW),
    ("Chose Postgres over MySQL for the billing database", MemoryKind.EPISODIC, 0.8,
     NOW - 120 * DAY),
    ("Chose Redis over Memcached for the billing cache", MemoryKind.EPISODIC, 0.8, NOW),
    ("Always run database migrations before deploying", MemoryKind.PROCEDURAL, 0.9,
     NOW - 300 * DAY),
]
for text, kind, importance, when in writes:
    result = store.remember(text, kind=kind, subject="akash",
                            importance=importance, now=when)
    status = "stored " if result else "DEDUP'D"
    print(f"  {status}  ({kind.value:<10}) {text[:52]}")

print(f"\n  {len(store)} memories stored from {len(writes)} writes")

print("\n" + "=" * 72)
print("2. RANKING: why similarity alone is not enough")
print("=" * 72)
query = "what did we choose for billing?"
print(f"  query: {query!r}\n")
print(f"  {'sim':>6} {'recency':>8} {'imp':>5} {'TOTAL':>7}  memory")
print("  " + "-" * 66)
for hit in store.vectors.search(query, k=6, where=lambda d: d.metadata["subject"] == "akash"):
    memory = store.all_memories("akash")
    m = next(x for x in memory if x.id == hit.document.id)
    rec = recency_weight(NOW - m.created_at) if m.kind is MemoryKind.EPISODIC else 1.0
    total = composite_score(hit.score, m, now=NOW)
    print(f"  {hit.score:>6.3f} {rec:>8.3f} {m.importance:>5.2f} {total:>7.3f}  "
          f"{m.text[:44]}")

print("""
  Look at the two 'Chose ...' rows. Similarity can barely tell them apart — both are
  about choosing something for billing. The 120-day-old one decays to a low recency
  weight and the current one wins. That tie-break is the entire reason for the
  composite score.

  Note the procedural memory keeps recency 1.000 despite being 300 days old. "Run
  migrations first" does not expire.

  NOW LOOK AT THE ROWS WITH sim = 0.000. Their totals (0.34-0.38) beat the relevant
  120-day-old Postgres memory (0.262), purely on importance and recency. That is a
  real weakness of any weighted blend: an important, fresh, COMPLETELY IRRELEVANT
  memory can outrank a relevant one.

  This is why `recall()` applies `min_similarity` BEFORE scoring. The floor removes
  the zero-similarity rows from consideration entirely; the composite score then
  only reorders things that were relevant to begin with. Filtering and ranking are
  different jobs, and a blend cannot do the filtering job.""")

print("\n" + "=" * 72)
print("3. UPDATING: a changed fact must REPLACE, not accumulate")
print("=" * 72)
job = next(m for m in store.all_memories("akash") if "Kryptos" in m.text)
print(f"  before: {job.text}")
store.update(job.id, "Akash now leads the AI team at Kryptos")
print(f"  after : {store.all_memories('akash')[0].text if False else store.vectors.get(job.id).text}")
print(f"  count : {len(store)} (unchanged — replaced, not appended)")
print("""
  If both versions were stored, recall would return both and the model would have to
  guess which is current. It guesses wrong roughly half the time, and you cannot tell
  from the output that anything went wrong.""")

print("\n" + "=" * 72)
print("4. WHAT THE MODEL ACTUALLY SEES")
print("=" * 72)
print(store.as_context(store.recall("billing database decisions", subject="akash",
                                    k=3, now=NOW)))
