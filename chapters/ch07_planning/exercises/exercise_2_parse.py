"""EXERCISE 2 — Parsing model-generated plans.

WHY: Everything in this file exists because a real model produced it. Markdown
fences, prose either side, string ids, missing fields, dependencies on steps that
don't exist, and 1->2->1 cycles are all things you will actually receive.

A bad plan does not raise — it HANGS. The executor loops, finds nothing ready, and
spins. Repair at parse time is far cheaper than diagnosing that at runtime.

    pytest chapters/ch07_planning/tests -q -k parse
"""

from __future__ import annotations

import json
from typing import Any

from .exercise_1_plan import Plan, PlanStep

PLANNER_PROMPT = """\
Break this goal into the smallest number of concrete steps that actually achieves it.

GOAL: {goal}

{context}

Rules:
- Each step must be a single concrete action, not a vague intention.
  BAD:  "research the topic"
  GOOD: "read config/database.yml and note the connection timeout"
- Use `depends_on` only for real ordering constraints. Steps with no dependency
  between them will be run in parallel, so unnecessary dependencies cost you time.
- 3 to 7 steps. If it needs more than 7, the goal is too big; make the last step
  "re-plan with what we have learned".
- Do not include a step for reporting the answer. That happens automatically.

Return ONLY a JSON array:
[{{"id": 1, "description": "...", "depends_on": []}}, ...]"""


def json_array(raw: str) -> list[Any]:
    """Pull a JSON array out of a model response. NEVER raises; [] on failure.

    Spec:
      * None/empty -> []
      * if "```" appears, take the LONGEST fence-delimited block (models put prose
        in the short ones and the payload in the long one), strip a leading "json"
      * slice from the first "[" to the last "]"
      * json.loads it; on JSONDecodeError -> []
      * result must be a list, else []
    """
    # TODO: implement
    raise NotImplementedError


def parse_plan(goal: str, raw: str) -> Plan:
    """Build a Plan from a model's JSON, repairing what you can.

    Spec, per item (enumerate from 1):
      * a plain STRING -> PlanStep(id=index, description=the string)
        (models sometimes ignore your schema and return ["do this", "do that"])
      * a dict:
          description = item["description"] or item["step"], stripped;
                        EMPTY -> skip the item entirely
          id          = int(item.get("id", index)); unparseable -> index
          depends_on  = each entry int()'d; unparseable entries dropped
      * anything else -> skip

    Then REPAIR, in this order:
      1. drop dependencies on ids that do not exist   (dangling -> deadlock)
      2. drop self-dependencies                        (step 2 depends on 2)
      3. break cycles: keep only dependencies on steps that appear EARLIER in the
         list. That is a crude topological repair and it is enough — it cannot
         produce a cycle, and for a numbered plan it preserves the intent.

    Every one of these repairs prevents a hang. None of them prevents a "wrong but
    runnable" plan; that is what re-planning is for.
    """
    # TODO: implement
    raise NotImplementedError
