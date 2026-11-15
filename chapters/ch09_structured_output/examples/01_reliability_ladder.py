"""The four techniques, and what each one is worth. Free and offline.

    python chapters/ch09_structured_output/examples/01_reliability_ladder.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.structured import extract_json, extract_validated, validate

SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "urgency": {"type": "integer", "minimum": 1, "maximum": 5},
        "topics": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "required": ["sentiment", "urgency", "topics"],
}

# Real shapes of model output, roughly in the proportions you actually see.
RESPONSES = [
    '{"sentiment": "negative", "urgency": 4, "topics": ["billing"]}',
    '```json\n{"sentiment": "negative", "urgency": 4, "topics": ["billing"]}\n```',
    'Here is the analysis:\n{"sentiment": "negative", "urgency": 4, "topics": ["billing"]}',
    '{"sentiment": "negative", "urgency": 4, "topics": ["billing"],}',
    '{"sentiment": "very negative", "urgency": 4, "topics": ["billing"]}',
    '{"sentiment": "negative", "urgency": "high", "topics": ["billing"]}',
    '{"sentiment": "negative", "urgency": 4}',
    "I'm not able to analyse that message.",
]

print("=" * 76)
print("STEP 3a: json.loads only  (the naive baseline)")
print("=" * 76)
import json

ok = 0
for raw in RESPONSES:
    try:
        json.loads(raw)
        ok += 1
    except json.JSONDecodeError:
        pass
print(f"  parsed: {ok}/{len(RESPONSES)}")

print("\n" + "=" * 76)
print("STEP 3b: + extract_json  (fences, prose, trailing commas)")
print("=" * 76)
parsed = [extract_json(r) for r in RESPONSES]
print(f"  parsed: {sum(p is not None for p in parsed)}/{len(RESPONSES)}")

print("\n" + "=" * 76)
print("STEP 3c: + validate  (parsing is not the same as being correct)")
print("=" * 76)
print(f"  {'response':<46} {'parsed':>7}  errors")
print("  " + "-" * 72)
valid = 0
for raw, value in zip(RESPONSES, parsed):
    if value is None:
        print(f"  {raw[:44]!r:<46} {'NO':>7}  not parseable")
        continue
    errors = validate(value, SCHEMA)
    valid += not errors
    detail = "ok" if not errors else errors[0]
    print(f"  {raw[:44]!r:<46} {'yes':>7}  {detail[:34]}")
print(f"\n  parseable: {sum(p is not None for p in parsed)}/{len(RESPONSES)}"
      f"   |   VALID: {valid}/{len(RESPONSES)}")
print("""
  Three of those parsed perfectly well and were still wrong. An enum violation,
  a string where an integer belongs, a missing field. `json.loads` succeeding
  tells you nothing about whether your program can use the result.""")

print("\n" + "=" * 76)
print("STEP 4: + the repair loop")
print("=" * 76)


def flaky_model(attempts):
    """A model that fixes its output once it is told what was wrong."""
    it = iter(attempts)

    def call(feedback):
        return next(it)
    return call


cases = {
    "bad enum, then fixed": [
        '{"sentiment": "very negative", "urgency": 4, "topics": ["billing"]}',
        '{"sentiment": "negative", "urgency": 4, "topics": ["billing"]}',
    ],
    "unparseable, then fixed": [
        "I can't do that.",
        '{"sentiment": "neutral", "urgency": 2, "topics": ["general"]}',
    ],
    "never fixes it": ["nope"] * 3,
}

for label, attempts in cases.items():
    result = extract_validated(flaky_model(attempts), SCHEMA, max_attempts=3)
    print(f"  {label:<26} ok={str(result.ok):<6} attempts={result.attempts}  "
          f"{'' if result.ok else result.errors[0][:30]}")

print("\n" + "=" * 76)
print("WHAT THE REPAIR PROMPT ACTUALLY SAYS")
print("=" * 76)
from agentlib.structured import repair_prompt

bad = extract_json('{"sentiment": "very negative", "urgency": "high"}')
print(repair_prompt(validate(bad, SCHEMA), SCHEMA, "")[:420])
print("""
  Compare that with "That was invalid, try again."

  A model told `$.urgency: expected integer, got str` fixes it next time,
  essentially always. A model told "invalid" re-emits something similar and you
  pay for another round. This one difference is the largest single lever in the
  chapter — measure it yourself in Exercise 5(d).""")
