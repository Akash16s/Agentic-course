"""EXERCISE 5 — Measure it: four retrievers, one golden set, one table.

No automated test. Runs offline; the reranker step optionally uses your OpenRouter key.

    python chapters/ch06b_retrieval/exercises/exercise_5_measure_it.py
    python chapters/ch06b_retrieval/exercises/exercise_5_measure_it.py --llm

The corpus, the golden set and an offline stand-in for an embedding model are below,
ready to use. Import the machinery from `agentlib.retrieval` (or from your own
exercises — they have the same interface).

TASKS
  1. Build four retrievers over CORPUS, each a function `(query, k) -> list[doc_id]`:
       a. vector only   VectorStore(ToySemanticEmbedder()), ids from .search
       b. BM25 only     BM25Index, ids from .search
       c. hybrid        HybridRetriever over the two, .search_ids
       d. hybrid + contextual headers: the same, but index
                        `with_header(title, text)` instead of the bare text

  2. Run `evaluate_retriever(fn, GOLDEN, k=5)` for each and print one row per
     retriever with `RetrievalReport.header(k)` and `report.row(name)`.

  3. Print a per-query table: for each golden query, the rank of the first relevant
     chunk under each retriever ('-' if it missed). Use `reciprocal_rank` on
     `report.per_query[i].retrieved`. This table is the one you learn from — the
     averages only tell you whether to look.

  4. With `--llm`: add a fifth retriever, "hybrid + headers + rerank". Retrieve 20
     with the header hybrid, rerank with `LLMReranker(LLMClient())`, keep the top k.
     Print `reranker.fallbacks` at the end. (~15 small calls, well under $0.01.)

  5. THEN INVESTIGATE — this is where the learning is:
       a. Which queries does BM25 miss, and which does vector search push down? Put
          each failure in one of three buckets: identifier, paraphrase, missing
          context. Every retrieval failure you meet in real life is one of these.
       b. Run with --k 1 and --k 3. Which retriever suffers most as k shrinks? That
          is the one whose RANKING is weak even when its RECALL looks fine.
       c. Set HybridRetriever weights to (1.0, 0.3) and then (0.3, 1.0). Where is
          the sweet spot ON THIS GOLDEN SET? Would you trust it with 15 queries?
       d. Set rrf_k to 1 and to 500. Does anything change? (Chapter section 4
          explains why it rarely does.)
       e. Add three queries of your own that you expect to fail, label them, and
          check you were right. A golden set grows from failures you have seen.
       f. Replace ToySemanticEmbedder with a real embedder (Chapter 6's warning box
          has the options). Re-run. Which conclusions survived?
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.embeddings import HashingEmbedder, tokenise
from agentlib.memory.vector import VectorStore  # noqa: F401  (you will need these)
from agentlib.retrieval import (  # noqa: F401
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


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
