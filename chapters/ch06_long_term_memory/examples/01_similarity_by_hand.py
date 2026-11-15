"""What an embedding actually is. Free and offline.

    python chapters/ch06_long_term_memory/examples/01_similarity_by_hand.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.embeddings import HashingEmbedder, cosine_similarity, tokenise

e = HashingEmbedder(dimensions=1024)

print("=" * 72)
print("1. A VECTOR IS JUST NUMBERS")
print("=" * 72)
v = e.embed("Postgres is our production database")
print("text  : Postgres is our production database")
print(f"tokens: {tokenise('Postgres is our production database')}")
print(f"vector: [{', '.join(f'{x:.3f}' for x in v[:6])}, ... ] ({len(v)} numbers)")
print(f"length: {sum(x * x for x in v) ** 0.5:.6f}   <- normalised to exactly 1")

print("\n" + "=" * 72)
print("2. SIMILARITY IS THE ANGLE BETWEEN TWO VECTORS")
print("=" * 72)
base = "Postgres is our production database"
for other in [
    "Postgres is our production database",
    "our production database is Postgres",
    "the production database runs Postgres 16",
    "Redis is our caching layer",
    "the coffee machine is broken",
]:
    print(f"  {cosine_similarity(e.embed(base), e.embed(other)):+.3f}  {other}")

print("\n" + "=" * 72)
print("3. MAGNITUDE IS IGNORED — THAT IS WHY WE USE COSINE")
print("=" * 72)
short = "Postgres database"
long_ = "Postgres database. " * 40
print(f"  short text ({len(short):>3} chars) vs long text ({len(long_):>3} chars): "
      f"{cosine_similarity(e.embed(short), e.embed(long_)):+.3f}")
print("  A two-line note and a two-page essay on the same topic point the same way.")
print("  Euclidean distance would call them far apart. You want them to match.")

print("\n" + "=" * 72)
print("4. THE LIMIT OF LEXICAL SEARCH")
print("=" * 72)
pairs = [("car", "automobile"), ("doctor", "physician"), ("big", "large"),
         ("Postgres", "Postgres")]
for a, b in pairs:
    print(f"  {cosine_similarity(e.embed(a), e.embed(b)):+.3f}  {a!r} vs {b!r}")
print("""
  A hashing embedder sees characters, not meaning. 'car' and 'automobile' hash to
  unrelated buckets and score 0.

  A trained embedding model scores those pairs around 0.85-0.95, because it learned
  from text where the words are used interchangeably. THAT is what you are buying
  when you pay for an embedding API, and it is the whole difference between lexical
  and semantic search.""")
