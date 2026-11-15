"""Vector search misses an error code. BM25 finds it. Then the reverse. Free, offline.

    python chapters/ch06b_retrieval/examples/01_where_vectors_fail.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.embeddings import HashingEmbedder, tokenise
from agentlib.memory.vector import VectorStore
from agentlib.retrieval import BM25Index, HybridRetriever

KB = {
    "kb-01": "Payment errors: what each error means and what to do when a payment error appears.",
    "kb-02": "Card declined at the terminal. Most declines are temporary and clear on retry. "
             "If the terminal shows E4012, the issuing bank refused the charge: ask the "
             "customer for another card. Check the network connection and the terminal "
             "firmware before escalating.",
    "kb-03": "Error E4013 means the card has expired. Ask for a different card.",
    "kb-04": "How to issue a refund from the dashboard. Refunds arrive in 5-10 business days.",
    "kb-05": "The payments API returns an error code in the error field of every failed response.",
    "kb-06": "Login error after a password reset: clear the browser cache.",
    "kb-07": "Webhook delivery errors are retried for 24 hours.",
    "kb-08": "Payout schedule: funds arrive in your bank account within two business days.",
    "kb-09": "Rate limit error 429: slow down and retry with backoff.",
    "kb-10": "Terminal setup: pair the card reader over Bluetooth.",
}
ANSWER = "kb-02"


def show(title, ids, answer):
    print(f"  {title}")
    for rank, doc_id in enumerate(ids, start=1):
        mark = "   <- the answer" if doc_id == answer else ""
        print(f"    {rank}. {doc_id}  {KB[doc_id][:52]:<54}{mark}")
    if answer not in ids:
        print(f"    ({answer} is not in the results)")


vectors = VectorStore(HashingEmbedder())
vectors.add_many(list(KB.values()), ids=list(KB))
bm25 = BM25Index()
bm25.add_many(KB.items())

print("=" * 76)
print("1. A SUPPORT AGENT IS ASKED ABOUT AN ERROR CODE")
print("=" * 76)
QUERY = "error E4012"
print(f"  query: {QUERY!r}    tokens: {tokenise(QUERY)}\n")
show("vector search, top 5:", [r.document.id for r in vectors.search(QUERY, k=5)], ANSWER)
print()
show("BM25, top 5:", [doc_id for doc_id, _ in bm25.search(QUERY, k=5)], ANSWER)

print("\n" + "=" * 76)
print("2. WHY: NOT ALL WORDS ARE WORTH THE SAME")
print("=" * 76)
for term in tokenise(QUERY):
    docs = [d for d in KB if term in tokenise(KB[d])]
    print(f"  {term:<8} appears in {len(docs):>2} of {len(KB)} docs   IDF = {bm25.idf(term):.2f}")
print("""
  The hashing embedder gives 'error' and 'e4012' the same weight, so short documents
  that say 'error' a lot win. BM25's IDF knows 'error' is everywhere and 'e4012' is
  nearly nowhere, so matching 'e4012' is worth ~3x as much.

  A REAL embedding model fails here too, for a worse reason: it splits 'E4012' into
  sub-word pieces ('E', '40', '12') and smooths them into "some error code". To it,
  E4012 and E4013 (kb-03, a different problem) look almost identical. Exact
  identifiers — error codes, SKUs, ticket numbers, function names, people's
  surnames — are where vector search is weakest and keyword search is strongest.""")

print("=" * 76)
print("3. THE REVERSE: KEYWORDS CANNOT SEE SYNONYMS")
print("=" * 76)
QUERY2 = "when do I get my money back?"
ANSWER2 = "kb-04"
print(f"  query: {QUERY2!r}    tokens: {tokenise(QUERY2)}\n")
hits = [doc_id for doc_id, _ in bm25.search(QUERY2, k=5)]
show("BM25, top 5:", hits, ANSWER2)


class ToySemanticEmbedder(HashingEmbedder):
    """A STAND-IN for a trained embedding model: maps a few synonyms onto one word
    before hashing. A real model learns millions of these from data; this one knows
    six. Enough to show the effect, offline."""

    SYNONYMS = {"money": "refund", "back": "refund", "refunds": "refund",
                "reimburse": "refund", "repaid": "refund", "rejected": "declined"}

    def embed(self, text):
        words = [self.SYNONYMS.get(w, w) for w in tokenise(text)]
        return super().embed(" ".join(words))


semantic = VectorStore(ToySemanticEmbedder())
semantic.add_many(list(KB.values()), ids=list(KB))
print()
show("'semantic' vector search, top 5:", [r.document.id for r in semantic.search(QUERY2, k=5)],
     ANSWER2)
print("""
  The user said 'money back'; the document says 'refund'. No shared word, so BM25
  cannot find it — its only hit matched the filler word 'do'. A model that has
  learned 'money back' and 'refund' mean the same thing finds it first.""")

print("=" * 76)
print("4. SO USE BOTH: HYBRID SEARCH")
print("=" * 76)
hybrid = HybridRetriever(VectorStore(ToySemanticEmbedder()), BM25Index())
hybrid.add_many(KB.items())
for query, answer in [(QUERY, ANSWER), (QUERY2, ANSWER2)]:
    print(f"  query: {query!r}")
    for rank, hit in enumerate(hybrid.search(query, k=3), start=1):
        mark = "   <- the answer" if hit.doc_id == answer else ""
        print(f"    {rank}. {hit.doc_id}  vector rank {str(hit.vector_rank):>4}  "
              f"bm25 rank {str(hit.bm25_rank):>4}{mark}")
    print()
print("""  Neither retriever alone gets both answers into its top 3; the hybrid does. Each
  covers the other's blind spot. The ORDER is still not perfect — that is the
  reranker's job (Exercise 4). Example 02 shows how the fusion works.""")
