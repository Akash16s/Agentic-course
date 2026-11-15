"""SOLUTION — Chapter 6, Exercise 3."""

from __future__ import annotations


def chunk_text(
    text: str,
    *,
    max_chars: int = 1_000,
    overlap: int = 150,
    separators: tuple[str, ...] = ("\n\n", "\n", ". ", " "),
) -> list[str]:
    """Split text into overlapping chunks, preferring natural boundaries.

    Two parameters, two reasons:

    `max_chars` — a chunk is the unit of retrieval. Too big and you retrieve a page
    to answer one sentence, diluting the context. Too small and you cut sentences in
    half and lose the meaning. 500-1500 characters is the usual sweet spot.

    `overlap` — a fact that straddles a boundary would otherwise be in neither chunk.
    Overlap means it is fully present in at least one. ~10-20% of max_chars.

    The separator list is a preference order: split on paragraphs if you can, then
    lines, then sentences, then words, and only hard-cut if a single "word" is longer
    than the chunk.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # Clamp the overlap to half the chunk. Without this, overlap >= max_chars makes
    # `start` advance by the +1 guard alone: 1,000 characters becomes ~900 chunks of
    # 100 characters each. It terminates, which is why the +1 is there, but it is
    # useless output and it looks like a hang.
    overlap = max(0, min(overlap, max_chars // 2))

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # walk the separators looking for a clean break near the end
            for separator in separators:
                cut = text.rfind(separator, start + max_chars // 2, end)
                if cut != -1:
                    end = cut + len(separator)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)  # the +1 guarantees progress
    return chunks
