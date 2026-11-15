"""SOLUTION — Chapter 9, Exercise 1."""

from __future__ import annotations

import json
import re
from typing import Any

FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> Any | None:
    """Pull a JSON value out of a model response. None on failure, never raises.

    Handles, in order of how often they happen:
      1. clean JSON
      2. JSON inside a ```json fence, with prose either side
      3. JSON with prose either side and no fence
      4. trailing commas before } or ]
      5. a leading "json" label

    It does NOT try to fix single quotes or unquoted keys. Past a certain point you
    are writing a JavaScript parser, and the right move is to send the error back to
    the model (see `repair_loop`) rather than guess at what it meant.
    """
    if not raw or not raw.strip():
        return None

    for candidate in candidates(raw):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = strip_trailing_commas(candidate)
            if repaired != candidate:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
    return None


def candidates(raw: str) -> list[str]:
    """Substrings that might be the JSON, best guess first."""
    text = raw.strip()
    out = [text]

    for block in FENCE.findall(text):
        out.append(block.strip())

    if text.lower().startswith("json"):
        out.append(text[4:].strip())

    # the widest {...} and [...] spans
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            out.append(text[start: end + 1])

    seen: set[str] = set()
    return [c for c in out if c and not (c in seen or seen.add(c))]


def strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)
