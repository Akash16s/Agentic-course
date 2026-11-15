"""EXERCISE 2 — Parsing Google-style docstrings.

WHY: Parameter descriptions are the highest-leverage prompt engineering in an agent, and
you already wrote them — in the docstring. Extracting them automatically means the
schema can never drift from the documentation.

    pytest chapters/ch02_tools/tests -q -k docstring
"""

from __future__ import annotations

import re

#: Matches the line that opens the parameter block.
ARGS_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters)\s*:\s*$", re.IGNORECASE)

#: Matches "    name: description" or "    name (int): description"
ARG_LINE = re.compile(r"^\s*(\*{0,2}\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$")

#: Sections that END the parameter block.
SECTION_END = re.compile(r"^\s*(Returns|Raises|Yields|Examples?)\s*:\s*$", re.IGNORECASE)


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """Split a docstring into (summary, {param_name: description}).

    Spec:
      * None or ""             -> ("", {})
      * everything before an Args:/Arguments:/Parameters: header is the summary,
        `.strip()`ped, newlines preserved in the middle
      * inside the Args block, each ARG_LINE match starts a new parameter
      * a non-matching, non-blank line inside the Args block is a CONTINUATION of the
        previous parameter's description — append it with a single space
      * a SECTION_END line ends the Args block
      * strip leading `*` from names, so `*args` is recorded as `args`
      * if there is no Args block, the whole docstring is the summary

    Example input:

        '''Look up the weather.

        Longer explanation here.

        Args:
            city: City name, e.g. "Delhi".
            unit (str): Temperature unit. Defaults to
                celsius if omitted.

        Returns:
            A description of the weather.
        '''

    -> summary: 'Look up the weather.\\n\\nLonger explanation here.'
       params : {'city': 'City name, e.g. "Delhi".',
                 'unit': 'Temperature unit. Defaults to celsius if omitted.'}
    """
    # TODO: implement
    raise NotImplementedError
