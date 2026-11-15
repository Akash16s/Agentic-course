"""Thirty skills: inlined into the prompt vs. indexed and loaded on demand. Free, offline.

Builds 30 throwaway skill folders in a temp directory, then measures the system prompt
both ways and prices a 40-step run.

    python chapters/ch08b_harness/examples/02_progressive_disclosure.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.harness import SkillRegistry
from agentlib.pricing import cost_usd
from agentlib.tokens import estimate_tokens

MODEL = "anthropic/claude-sonnet-4.5"
STEPS = 40                    # calls in one longish agent run
SKILLS_USED = 2               # how many skills a typical task actually needs
TOPICS = [
    "pdf-forms", "sql-style", "release-notes", "git-bisect", "csv-cleanup",
    "invoice-matching", "terraform-plan", "k8s-debug", "api-pagination", "unit-tests",
    "log-triage", "data-migration", "email-drafts", "brand-voice", "accessibility",
    "perf-profiling", "security-review", "dependency-upgrade", "i18n-strings",
    "chart-styling", "excel-formulas", "pptx-decks", "docx-reports", "oncall-handoff",
    "incident-review", "pricing-tables", "regex-recipes", "sql-migrations",
    "feature-flags", "changelog",
]

base_system = "You are a helpful engineering agent. Use your tools; be concise."

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for topic in TOPICS:
        folder = root / topic
        folder.mkdir()
        body = "\n".join(
            f"{i}. When doing {topic}, step {i}: check the inputs, follow the house "
            f"convention, and verify the output before moving on."
            for i in range(1, 61)
        )                                                   # ~7k chars, a realistic size
        (folder / "SKILL.md").write_text(
            f"---\nname: {topic}\n"
            f"description: How we do {topic.replace('-', ' ')}. Use when the task "
            f"involves {topic.replace('-', ' ')}.\n---\n# {topic}\n\n{body}\n"
        )

    registry = SkillRegistry(root)

    inlined = base_system + "\n\n" + "\n\n".join(
        f"## Skill: {n}\n{registry.get(n).body}" for n in registry.names
    )
    indexed = base_system + "\n\n" + registry.index_prompt(max_chars=4000)

    inlined_tok = estimate_tokens(inlined)
    indexed_tok = estimate_tokens(indexed)
    body_tok = estimate_tokens(registry.get(TOPICS[0]).body)

    print("=" * 70)
    print(f"SYSTEM PROMPT SIZE — {len(registry)} skills, ~{body_tok:,} tokens of body each")
    print("=" * 70)
    print(f"  everything inlined : {inlined_tok:>8,} tokens")
    print(f"  index only         : {indexed_tok:>8,} tokens   "
          f"({inlined_tok / indexed_tok:.0f}x smaller)")

    # A run: the system prompt is re-sent on every call. With the index, the bodies
    # of the skills actually used enter the history once (as tool results) and are
    # then re-sent on every later call too — but only those.
    inlined_run = inlined_tok * STEPS
    loaded_tok = SKILLS_USED * body_tok
    indexed_run = indexed_tok * STEPS + loaded_tok * (STEPS - 2)   # loaded early

    print(f"\n{'=' * 70}\nONE {STEPS}-STEP RUN (system prompt + loaded skills only)\n{'=' * 70}")
    print(f"  inlined : {inlined_run:>10,} input tokens  ${cost_usd(MODEL, inlined_run, 0):.3f}")
    print(f"  indexed : {indexed_run:>10,} input tokens  ${cost_usd(MODEL, indexed_run, 0):.3f}"
          f"   ({SKILLS_USED} skills loaded on step 1-2)")
    print(f"  -> {inlined_run / indexed_run:.1f}x cheaper, before prompt caching")
    print(f"""
  Prompt caching (Chapter 13) narrows the money gap: a cached prefix is billed at a
  fraction of the normal rate. It does NOT fix the other two problems:
    * the window: {inlined_tok:,} tokens of instructions leave less room for work
    * attention: 30 sets of instructions bury the 2 that matter (Chapter 4, §3)""")

    print(f"\n{'=' * 70}\nTHE INDEX THE MODEL SEES (first 6 lines)\n{'=' * 70}")
    for line in registry.index_prompt(max_chars=4000).splitlines()[:6]:
        print("  " + line[:100])

    print(f"\n{'=' * 70}\nA TIGHT BUDGET — max_chars=900\n{'=' * 70}")
    tight = registry.index_prompt(max_chars=900)
    for line in tight.splitlines()[-3:]:
        print("  " + line[:100])
    print(f"  ({len(tight)} chars)")
    print("""
  The last line matters. Without "(+N more skills not listed)", a model that does
  not see a skill assumes it does not exist and improvises instead.

  The description is the whole interface. "Helps with PDFs" will be loaded for
  every task that mentions a PDF, or never. "Fill in PDF forms. Use when the user
  gives you a .pdf with form fields" gets loaded when it should be.""")
