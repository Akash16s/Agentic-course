"""When reflection helps, and when it is expensive theatre. Free and offline.

    python chapters/ch07_planning/examples/02_reflection_or_theatre.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.planning import Critique, reflect_loop

print("=" * 74)
print("CASE A: the critic CAN check something (a JSON schema)")
print("=" * 74)

REQUIRED = {"name", "email", "role"}
attempts = iter([
    '{"name": "Akash"}',
    '{"name": "Akash", "email": "a@example.com"}',
    '{"name": "Akash", "email": "a@example.com", "role": "engineer"}',
])


def produce_json(feedback):
    return next(attempts)


def validating_critic(task, answer):
    """Has access to something the producer did not use: the actual schema."""
    try:
        obj = json.loads(answer)
    except json.JSONDecodeError as exc:
        return Critique(False, [f"not valid JSON: {exc}"], "return valid JSON")
    missing = REQUIRED - set(obj)
    if missing:
        return Critique(False, [f"missing fields: {sorted(missing)}"],
                        f"add {sorted(missing)}")
    return Critique(acceptable=True)


answer, critiques = reflect_loop("produce a user record", produce_json,
                                 validating_critic, max_rounds=4)
for i, c in enumerate(critiques):
    print(f"  round {i}: {'ACCEPT' if c.acceptable else 'REJECT'}  {c.summary}")
print(f"  final : {answer}")
print("""
  This works, and it works reliably. The critic ran a check the producer did not:
  it compared the output against a real schema. The feedback is factual, and the
  producer can act on it. Three rounds, a correct answer, and you could prove it.""")

print("\n" + "=" * 74)
print("CASE B: the critic has NOTHING the producer didn't")
print("=" * 74)

versions = iter([
    "Photosynthesis converts light into chemical energy.",
    "Photosynthesis is the process by which plants convert light into chemical energy.",
    "Photosynthesis is how plants turn sunlight into stored chemical energy.",
    "Plants use photosynthesis to convert sunlight into chemical energy they store.",
])
generated_objections = iter([
    "could be clearer about the mechanism",
    "could mention the role of chlorophyll",
    "the phrasing is a little dry",
])


def produce_prose(feedback):
    return next(versions)


def opinion_critic(task, answer):
    """Same information as the producer. Asked to find fault, it finds fault."""
    objection = next(generated_objections, None)
    if objection is None:
        return Critique(acceptable=True)
    return Critique(False, [objection], f"revise: {objection}")


answer, critiques = reflect_loop("explain photosynthesis in one sentence",
                                 produce_prose, opinion_critic, max_rounds=4)
for i, c in enumerate(critiques):
    print(f"  round {i}: {'ACCEPT' if c.acceptable else 'REJECT'}  {c.summary}")
print(f"  final : {answer}")
print(f"\n  cost  : 4 producer calls + 4 critic calls = 8 calls")
print(f"  gain  : a differently-worded sentence")
print("""
  Every objection here is GENERATED, not found. There is no ground truth for "is
  this clear enough", so a model asked to criticise will comply indefinitely — you
  chose when to stop, not the critic.

THE TEST, and it is the only one that matters:

    Does the critic have information the producer did not?

  a compiler · a test suite · a JSON schema · the retrieved sources · a checklist
  · a different model · the actual output of running the code

  If the answer is no, you are paying 2-3x for a paraphrase. Measure it (Chapter
  10) before you ship it — on some tasks reflection measurably makes things WORSE,
  because the critic talks the producer out of a correct answer.""")
