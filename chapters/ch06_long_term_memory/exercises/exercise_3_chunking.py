"""EXERCISE 3 — Chunking.

    pytest chapters/ch06_long_term_memory/tests -q -k chunking
"""

from __future__ import annotations


def chunk_text(
    text: str,
    *,
    max_chars: int = 1_000,
    overlap: int = 150,
    separators: tuple[str, ...] = ("\n\n", "\n", ". ", " "),
) -> list[str]:
    """Split text into overlapping chunks that prefer natural boundaries.

    Spec:
      1. `text = text.strip()`; empty -> []
      2. len(text) <= max_chars -> [text]
      2b. CLAMP: `overlap = max(0, min(overlap, max_chars // 2))`
          Without this, overlap >= max_chars means `start` only advances by the +1
          guard below: 1,000 characters becomes ~900 chunks. It terminates, but the
          output is useless and it looks like a hang.
      3. walk from `start = 0`:
           end = min(start + max_chars, len(text))
           if end < len(text):
               for each separator in order, look for the LAST occurrence in
               text[start + max_chars//2 : end]  (i.e. `text.rfind(sep, lo, hi)`).
               First one found wins: set end = cut + len(separator), stop looking.
           append text[start:end].strip() if non-empty
           if end >= len(text): stop
           start = max(end - overlap, start + 1)
      4. return the chunks

    THE `start + 1` IS NOT OPTIONAL. Without it, a case where `end - overlap <= start`
    makes `start` stop advancing and you get an infinite loop that appends the same
    chunk until you run out of memory. It is the classic chunker bug.

    Searching only the SECOND HALF of the window for a boundary stops the chunker
    from producing tiny chunks: if a paragraph break happens to sit 20 characters in,
    you do not want a 20-character chunk.

    Overlap exists so a fact spanning a boundary is whole in at least one chunk:

        ...the timeout is set to | 30 seconds in production...
                       chunk 1 ──┘ └── chunk 2      neither answers the question
    """
    # TODO: implement
    raise NotImplementedError
