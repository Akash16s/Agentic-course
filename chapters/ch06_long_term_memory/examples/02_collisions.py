"""Why dimensionality matters: hash collisions producing fake similarity.

    python chapters/ch06_long_term_memory/examples/02_collisions.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.embeddings import HashingEmbedder
from agentlib.memory.vector import VectorStore

DOCS = [
    "Postgres 16 is our primary production database",
    "Redis handles session caching and rate limiting",
    "The billing service runs on Kubernetes in eu-west-1",
    "Our frontend is React with TypeScript",
]
QUERY = "which database do we use?"

print(f"query: {QUERY!r}\n")
print(f"{'dims':>6}  top result")
print("-" * 68)
for dims in (32, 64, 128, 256, 1024, 4096):
    store = VectorStore(HashingEmbedder(dimensions=dims))
    store.add_many(DOCS)
    top = store.search(QUERY, k=1)[0]
    correct = "Postgres" in top.text
    flag = "  <- correct" if correct else "  <- WRONG"
    print(f"{dims:>6}  {top.score:.3f}  {top.text[:42]:<44}{flag}")

print("-" * 68)
print("""
At low dimensions, unrelated words hash into the same bucket. The store then reports
real similarity between documents that share no words at all, and a document that
does not contain 'database' outranks the one that does.

Nothing errors. The scores look plausible. The answer is just wrong.

Real embedding models use 384-3072 dimensions for the same reason — though theirs
are learned, not hashed, so each dimension carries meaning rather than being a
bucket. Collisions are not the only reason for high dimensionality, but they are the
one you can watch happen.

This is also why `min_score` matters: at dims=32 every score is inflated by noise,
so any threshold you calibrated at dims=1024 would let the junk straight through.""")
