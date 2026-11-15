"""EXERCISE 4 — Handoffs and synthesis.

    pytest chapters/ch08_multi_agent/tests -q -k synthesis
"""

from __future__ import annotations

from dataclasses import dataclass

from .exercise_3_orchestrator import WorkerResult


@dataclass
class Handoff:
    """One agent passing control to another.

    Fields: target: str, reason: str = "", context: str = ""

    `context` is the field everyone forgets, and forgetting it is why handoffs feel
    broken: the receiving agent starts from nothing and asks the user to repeat what
    they already said. Everyone has had this experience with a human support
    transfer; it is exactly as annoying from a machine.

    Summarise into `context` — do not forward the whole transcript. The full history
    costs tokens and drags the first agent's dead ends into the second's window.
    """

    target: str

    def describe(self) -> str:
        """One line for a log or a trace:
            "-> {target}: {reason}"  (omit the ": {reason}" when there is no reason)
        """
        # TODO: implement
        raise NotImplementedError


def synthesis_prompt(goal: str, results: list[WorkerResult]) -> str:
    """Build the synthesiser's input from worker outputs.

    Spec:
      * start with "GOAL: {goal}" and a blank line
      * a header line introducing the findings
      * for each result, a labelled section:
            --- {name} ---
            {output}                       if ok
            [FAILED: {error}]              if not
      * end with an instruction to answer using ONLY these findings, and to say what
        is missing where a worker failed

    INCLUDING THE FAILURES IS THE POINT OF THIS FUNCTION. A synthesiser that cannot
    see that the pricing worker died will write a confident paragraph about pricing
    anyway, because the goal mentioned pricing and nothing contradicted it. This is
    the most common bug in the orchestrator-worker pattern and it is invisible in the
    output — the answer looks complete.
    """
    # TODO: implement
    raise NotImplementedError
