"""SOLUTION — Chapter 8, Exercise 4."""

from __future__ import annotations

from dataclasses import dataclass

from .exercise_3_orchestrator import WorkerResult


@dataclass
class Handoff:
    """One agent passing control to another.

    `context` is the part people leave out, and leaving it out is why handoffs fail:
    the receiving agent starts from nothing and asks the user to repeat themselves.
    """

    target: str
    reason: str = ""
    context: str = ""

    def describe(self) -> str:
        return f"-> {self.target}" + (f": {self.reason}" if self.reason else "")

def synthesis_prompt(goal: str, results: list[WorkerResult]) -> str:
    """Build the synthesiser's input from worker outputs.

    Failures are INCLUDED, labelled. A synthesiser that cannot see that the pricing
    research failed will happily write a confident paragraph about pricing.
    """
    lines = [f"GOAL: {goal}", "", "Findings from each worker:"]
    for result in results:
        lines.append(f"\n--- {result.name} ---")
        lines.append(result.output if result.ok else f"[FAILED: {result.error}]")
    lines.append(
        "\nWrite a single coherent answer to the goal using only the findings above. "
        "Where a worker failed, say what is missing rather than guessing."
    )
    return "\n".join(lines)
