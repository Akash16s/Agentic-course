"""SOLUTION — Chapter 6b, Exercise 5. Runs offline; `--llm` adds the reranker.

    python chapters/ch06b_retrieval/solutions/exercise_5_measure_it.py
    python chapters/ch06b_retrieval/solutions/exercise_5_measure_it.py --llm
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.embeddings import HashingEmbedder, tokenise
from agentlib.memory.vector import VectorStore
from agentlib.retrieval import (
    BM25Index,
    GoldenQuery,
    HybridRetriever,
    LLMReranker,
    RetrievalReport,
    evaluate_retriever,
    reciprocal_rank,
)

# --------------------------------------------------------------------- the data
# A help centre for a made-up payments product, already chunked: (id, title, text).
# Note that some chunks never mention their own topic — "Charge it for 2 hours"
# only makes sense under the title "Terminal T2". That is what real chunks look like.

CORPUS: list[tuple[str, str, str]] = [
    ("pay-01", "Refunds", "Open the payment in the dashboard, choose Refund and confirm the "
               "amount. Partial refunds are allowed."),
    ("pay-02", "Refunds", "Refunds arrive on the customer's card in 5 to 10 business days. "
               "The processing fee is not returned."),
    ("pay-03", "Disputes", "When a cardholder complains to their bank about a charge, you have "
               "7 days to upload evidence such as receipts and delivery tracking."),
    ("pay-04", "Disputes", "If you lose a dispute, the amount plus a 15 dollar fee is deducted "
               "from your next payout."),
    ("err-01", "Terminal error codes", "E4012: the issuing bank declined the card. Ask for "
               "another card or a different payment method."),
    ("err-02", "Terminal error codes", "E4013: the card has expired. Ask the customer for a "
               "different card."),
    ("err-03", "Terminal error codes", "E5001: the reader lost its network connection. Check "
               "the Wi-Fi and restart the reader."),
    ("err-04", "API errors", "HTTP 429 means you sent too many requests. Back off exponentially "
               "and retry."),
    ("err-05", "API errors", "HTTP 401 means the API key is missing or revoked. Generate a new "
               "key in Settings."),
    ("acc-01", "Payouts", "Payouts are sent to your bank account every weekday. The first "
               "payout takes 7 days."),
    ("acc-02", "Payouts", "To change the bank account that receives payouts, go to Settings "
               "then Banking."),
    ("acc-03", "Account security", "Turn on two-factor authentication under Settings then "
               "Security. Authenticator apps and SMS codes are supported."),
    ("acc-04", "Account security", "Forgot your password? Use the reset link on the sign-in "
               "page. The link expires after 1 hour."),
    ("dev-01", "Webhooks", "We notify your server about events such as payment.succeeded. "
               "Failed deliveries are retried for 3 days."),
    ("dev-02", "Webhooks", "Check the Signature header against your signing secret to reject "
               "forged requests."),
    ("dev-03", "SDKs", "Official libraries exist for Python, Node and Go. Install the Python "
               "package with pip install paykit."),
    ("hw-01", "Terminal T2", "Pair the reader with the app over Bluetooth and keep it within "
              "10 metres of the phone."),
    ("hw-02", "Terminal T2", "Charge it for 2 hours before first use. A full charge lasts "
              "for about 300 transactions."),
    ("pl-01", "Plans and pricing", "Starter costs nothing per month and charges 2.9 percent "
              "per transaction."),
    ("pl-02", "Plans and pricing", "Pro costs 30 dollars per month, lowers fees to 2.4 percent "
              "and adds multi-user access."),
    ("pl-03", "Plans and pricing", "Cancel at any time from Settings then Billing. You keep "
              "access until the end of the billing period."),
    ("tax-01", "Invoices and tax", "Download monthly invoices as PDF from the Billing page. "
               "VAT is shown on its own line."),
]

GOLDEN: list[GoldenQuery] = [
    # exact identifiers — keyword territory
    GoldenQuery("what does E4012 mean", {"err-01"}),
    GoldenQuery("terminal shows E5001", {"err-03"}),
    GoldenQuery("HTTP 401", {"err-05"}),
    GoldenQuery("pip install", {"dev-03"}),
    # paraphrase — vector territory
    GoldenQuery("when will the customer get their money back", {"pay-02"}),
    GoldenQuery("how do I fight a chargeback", {"pay-03", "pay-04"}),
    GoldenQuery("when do I get paid", {"acc-01"}),
    GoldenQuery("how do I enable 2fa", {"acc-03"}),
    GoldenQuery("stop my subscription", {"pl-03"}),
    # the topic lives in the TITLE, not the chunk — contextual headers territory
    GoldenQuery("T2 battery life", {"hw-02"}),
    GoldenQuery("connect the T2 over bluetooth", {"hw-01"}),
    GoldenQuery("how much does the Pro plan cost", {"pl-02"}),
    # ordinary queries both should get
    GoldenQuery("too many requests error", {"err-04"}),
    GoldenQuery("verify webhook signature", {"dev-02"}),
    GoldenQuery("download invoices", {"tax-01"}),
]


class ToySemanticEmbedder(HashingEmbedder):
    """A STAND-IN for a trained embedding model, so this runs offline.

    It imitates the two habits of real embedding models that matter here:

      1. SYNONYMS land together. It canonicalises a handful before hashing. A real
         model learns millions of these; this one knows the few this corpus needs.
      2. IDENTIFIERS get blurred. A real model splits "E4012" into sub-word pieces
         and ends up with "some error code"; here every token with 2+ digits is
         reduced to its shape, so E4012, E4013 and E5001 all become "e####".

    Swap in a real `Embedder` (see Chapter 6) to measure for real.
    """

    SYNONYMS = {
        "money": "refund", "back": "refund", "refunds": "refund",
        "chargeback": "dispute", "disputes": "dispute", "fight": "dispute",
        "paid": "payout", "payouts": "payout",
        "2fa": "two-factor", "enable": "turn",
        "subscription": "plan", "stop": "cancel",
        "connect": "pair",
    }

    def embed(self, text: str):
        words = [self.SYNONYMS.get(w, w) for w in tokenise(text)]
        words = [re.sub(r"\d", "#", w) if sum(c.isdigit() for c in w) >= 2 else w
                 for w in words]
        return super().embed(" ".join(words))


# ---------------------------------------------------------------- retrievers


def with_header(title: str, text: str) -> str:
    """Contextual chunk header: the chunk, prefixed with where it came from."""
    return f"{title}\n{text}"


def build(headers: bool) -> HybridRetriever:
    hybrid = HybridRetriever(VectorStore(ToySemanticEmbedder()), BM25Index())
    hybrid.add_many(
        [(doc_id, with_header(title, text) if headers else text)
         for doc_id, title, text in CORPUS],
        metadatas=[{"title": title} for _, title, _ in CORPUS],
    )
    return hybrid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true",
                        help="add an LLM reranker (needs OPENROUTER_API_KEY)")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    k = args.k

    plain, headed = build(headers=False), build(headers=True)

    retrievers = {
        "vector only": lambda q, k: [r.document.id for r in plain.vector_store.search(q, k=k)],
        "bm25 only": lambda q, k: [d for d, _ in plain.bm25.search(q, k=k)],
        "hybrid": plain.search_ids,
        "hybrid + headers": headed.search_ids,
    }

    reranker = None
    if args.llm:
        if not os.getenv("OPENROUTER_API_KEY"):
            sys.exit("--llm needs OPENROUTER_API_KEY in your environment or .env")
        from agentlib.llm import LLMClient

        reranker = LLMReranker(LLMClient())

        def reranked(query: str, k: int) -> list[str]:
            # retrieve wide, rerank narrow
            hits = headed.search(query, k=20)
            ranked = reranker.rerank(query, [(h.doc_id, h.text) for h in hits], top_n=k)
            return [r.doc_id for r in ranked]

        retrievers["hybrid+headers+rerank"] = reranked

    reports: dict[str, RetrievalReport] = {
        name: evaluate_retriever(fn, GOLDEN, k=k) for name, fn in retrievers.items()
    }

    print(f"\n{len(CORPUS)} chunks, {len(GOLDEN)} golden queries, k = {k}\n")
    print(RetrievalReport.header(k))
    print("-" * 72)
    for name, report in reports.items():
        print(report.row(name))

    # Per query: the rank of the first relevant document, per retriever. This is the
    # table you actually learn from — the averages only tell you WHETHER to look.
    print(f"\nrank of the first relevant chunk ('-' = not in the top {k})\n")
    names = list(reports)
    labels = {"vector only": "vector", "bm25 only": "bm25", "hybrid": "hybrid",
              "hybrid + headers": "+headers", "hybrid+headers+rerank": "+rerank"}
    short = [labels.get(n, n[:11]) for n in names]
    print(f"{'query':<46}" + "".join(f"{s:>12}" for s in short))
    print("-" * (46 + 12 * len(names)))
    for i, golden in enumerate(GOLDEN):
        cells = []
        for name in names:
            rr = reciprocal_rank(reports[name].per_query[i].retrieved, golden.relevant)
            cells.append(f"{round(1 / rr) if rr else '-':>12}")
        print(f"{golden.query[:45]:<46}" + "".join(cells))

    if reranker is not None:
        print(f"\nreranker fallbacks: {reranker.fallbacks} of {len(GOLDEN)} calls")
    else:
        print("\n(add --llm to include an LLM reranker; ~15 small calls, well under $0.01)")


if __name__ == "__main__":
    main()
