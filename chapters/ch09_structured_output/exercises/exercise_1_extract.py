"""EXERCISE 1 — Getting JSON out of a text response.

    pytest chapters/ch09_structured_output/tests -q -k extract
"""

from __future__ import annotations

import json
import re
from typing import Any

FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def candidates(raw: str) -> list[str]:
    """Substrings that might be the JSON, best guess FIRST.

    Spec — build the list in this order, then de-duplicate while PRESERVING ORDER
    (a dict or a seen-set, not `set()`):
      1. raw.strip() itself
      2. every fenced block (FENCE.findall), stripped
      3. if the text starts with "json" (any case), the text after those 4 chars
      4. the widest {...} span, then the widest [...] span
         (first "{" to last "}"; only if the last is after the first)

    Order matters: a clean parse of the whole string is the common case and should
    not be beaten by a lucky brace match inside prose.
    """
    # TODO: implement
    raise NotImplementedError


def strip_trailing_commas(text: str) -> str:
    """Remove commas immediately before a closing } or ].

    `re.sub(r",(\\s*[}\\]])", r"\\1", text)`

    Models emit these constantly — it is valid JavaScript and invalid JSON, and the
    training data is full of JavaScript.
    """
    # TODO: implement
    raise NotImplementedError


def extract_json(raw: str) -> Any | None:
    """Pull a JSON value out of a model response. NEVER raises; None on failure.

    Spec:
      * empty/whitespace -> None
      * for each candidate, in order:
          - try json.loads
          - on failure, try again after strip_trailing_commas (but only if that
            actually changed the text — no point parsing the same string twice)
      * nothing parsed -> None

    WHERE TO STOP: do not try to fix single quotes, unquoted keys or Python
    literals (True/None). Past that point you are writing a JavaScript parser, and
    the right move is to send the error back to the model — it repairs its own
    output far more accurately than your regex guesses at what it meant.
    """
    # TODO: implement
    raise NotImplementedError
