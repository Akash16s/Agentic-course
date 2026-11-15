"""Requirement 10: the eval runner and the CI gate.

    python evals/run.py            # full suite
    python evals/run.py --smoke    # 10 cases, for every commit
"""

from __future__ import annotations

import sys

from agentlib.evals.core import Dataset, EvalRunner


GATE = 0.0  # TODO: set to your BASELINE minus the noise, then ratchet up.
            # An aspirational gate is always red, and a gate that is always red
            # gets disabled.


def main() -> int:
    raise NotImplementedError
    # dataset = Dataset.from_jsonl("evals/dataset.jsonl")
    # if "--smoke" in sys.argv:
    #     dataset = dataset.filter(tag="smoke")
    # report = EvalRunner(run_case, build_checks(judge), max_parallel=4).run(dataset)
    # print(report.summary())
    # print(report.failure_detail())
    # append report.to_dict() to evals/history.jsonl so you can plot drift
    # return 0 if report.meets(GATE) else 1


if __name__ == "__main__":
    sys.exit(main())
