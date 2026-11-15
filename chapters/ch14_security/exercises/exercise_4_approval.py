"""EXERCISE 4 — Human in the loop.

    pytest chapters/ch14_security/tests -q -k approval
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class ApprovalRequest:
    """tool: str, arguments: dict, reason: str = "" """

    tool: str
    arguments: dict[str, Any]


class ApprovalQueue:
    """Collects tool calls that need a human decision.

    Deliberately simple — in production this is a database table and a UI. The
    shape is what matters, and one method matters more than the rest: `describe`.

    THE DESIGN FAILURE IS ALMOST NEVER "WE FORGOT TO ASK". It is asking in a way
    nobody can answer:

        BAD    Approve send_email? [y/N]
        GOOD   send_email(to='412 recipients', subject='Your account has been closed')

    A human approving the first has not made a decision, they have pressed a key.
    And if you ask forty times an hour they will approve everything by reflex, at
    which point the gate is decoration.
    """

    def __init__(self) -> None:
        """self.pending: list[ApprovalRequest], self.decisions: dict[int, bool],
        a threading.Lock."""
        # TODO: implement
        raise NotImplementedError

    def request(self, tool: str, arguments: dict[str, Any], reason: str = "") -> int:
        """Queue a request; return its index. COPY the arguments dict — the caller
        may reuse or mutate theirs, and an approval that changes after it was shown
        to a human is worse than no approval."""
        # TODO: implement
        raise NotImplementedError

    def resolve(self, index: int, approved: bool) -> None:
        # TODO: implement
        raise NotImplementedError

    def approved(self, index: int) -> bool | None:
        """True / False / None for "not decided yet".

        Three states, not two. `False` for undecided would auto-deny everything the
        moment a human is slow, which looks exactly like a bug.
        """
        # TODO: implement
        raise NotImplementedError

    def describe(self, index: int) -> str:
        """A line a human can actually judge:

            send_email(to='a@b.com', subject='Closed')
              reason: the user asked to close their account

        Include the reason line only when there is one. Show the ARGUMENTS — the
        tool name alone is not a decision.
        """
        # TODO: implement
        raise NotImplementedError
