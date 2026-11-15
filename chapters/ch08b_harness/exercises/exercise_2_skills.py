"""EXERCISE 2 — Skills: many capabilities, small prompt.

WHY: You want your agent to know how to fill PDF forms, write SQL in house style,
cut a release and forty other things. Pasting forty sets of instructions into the
system prompt costs ~80k tokens on EVERY call and buries the one that matters. So:
put each in a folder with a SKILL.md, list only the names and one-line descriptions
in the prompt, and let the model load a body when it decides it needs one.

    pytest chapters/ch08b_harness/tests -q -k skills

The file format:

    skills/
      pdf-forms/
        SKILL.md          <- required
        scripts/fill.py   <- optional extra files the body can point to
      sql-style/
        SKILL.md

    ---
    name: pdf-forms
    description: Fill in PDF forms. Use when the user gives you a .pdf with fields.
    ---
    # Filling PDF forms
    1. List the fields first...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from agentlib.tools import Tool, build_tool


class SkillError(ValueError):
    """A SKILL.md that cannot be used, or a request for a skill that does not exist."""


#: Lowercase letters, digits and hyphens, not starting with a hyphen.
SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

#: First line of the index. Mentions load_skill so the model knows how to get a body.
INDEX_HEADER = (
    "Skills you can load. Each line is `name: when to use it`. Before starting a task "
    "a skill covers, call load_skill(name) to read its full instructions."
)


@dataclass
class Skill:
    """Fields: name, description, body, path: Path|None = None,
    metadata: dict[str, str] (any other frontmatter keys)"""

    name: str
    description: str
    body: str
    path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def parse_skill(text: str, *, path: Path | None = None) -> Skill:
    """Parse one SKILL.md.

    Spec:
      1. Strip a leading BOM ("\\ufeff") and leading whitespace, then split into lines.
      2. The first line must be exactly "---" (after .strip())
         -> else SkillError mentioning 'frontmatter'
      3. Find the NEXT line that is "---". None -> SkillError mentioning 'closed'
      4. Every line between them:
           * blank, or starting with "#"  -> skip
           * no ":" in it                 -> SkillError
           * otherwise split on the FIRST ":" only (descriptions contain colons),
             strip key and value, and if the value is wrapped in matching ' or "
             quotes, remove them
      5. "name" and "description" must both be present and non-empty
         -> else SkillError naming the missing field
      6. name must match SKILL_NAME -> else SkillError mentioning 'name'
      7. body = everything after the closing "---", joined with "\\n", .strip()-ed
      8. any other keys -> `metadata`

    This is "YAML-ish" on purpose: real frontmatter is YAML, but name/description
    are all you need, and a 30-line parser you understand beats a dependency.
    """
    # TODO: implement
    raise NotImplementedError


class SkillRegistry:
    """Discover skills under a root folder. Index them cheaply, load them on demand.

    __init__(self, root):
      * self.root = Path(root); not a directory -> FileNotFoundError
        (a typo in the path silently giving you zero skills is a miserable bug)
      * self._skills: dict[str, Skill] = {}
      * self.errors: dict[str, str] = {}   folder name -> why it was skipped
      * self.loaded: list[str] = []        names, in the order load() was called
      * for each `root/*/SKILL.md` in sorted order (ONE level deep — use glob):
            parse it with path=<its folder>
            SkillError       -> self.errors[folder] = str(exc); skip it
            name already seen -> self.errors[folder] = "duplicate skill name '...'"
            otherwise store it under skill.name (NOT the folder name)

    One broken SKILL.md must not take the other forty down with it.
    """

    def __init__(self, root: str | Path) -> None:
        # TODO: implement
        raise NotImplementedError

    @property
    def names(self) -> list[str]:
        """Skill names, sorted."""
        # TODO: implement
        raise NotImplementedError

    def __len__(self) -> int:
        # TODO: implement
        raise NotImplementedError

    def __contains__(self, name: object) -> bool:
        # TODO: implement
        raise NotImplementedError

    def get(self, name: str) -> Skill | None:
        # TODO: implement
        raise NotImplementedError

    def index_prompt(self, *, max_chars: int = 2000, max_description_chars: int = 200) -> str:
        """The part of the system prompt that advertises the skills. Names and
        descriptions ONLY — never bodies.

        Spec:
          * no skills -> "" (do not spend tokens announcing nothing)
          * line 0 is INDEX_HEADER
          * then one line per skill in name order: f"- {name}: {description}"
            where a description longer than max_description_chars is cut to
            description[:max_description_chars - 3] + "..."
          * BUDGET: the whole result ("\\n".join(lines)) must be <= max_chars.
            Before adding skill i, check that the text would still fit WITH a note
            for the skills still remaining after it, "(+N more skills not listed)".
            If it would not fit, append the note for the skills not yet listed
            (including skill i) and stop.
          * if everything fits, there is no note

        The note matters: a model that does not know a list was cut assumes the
        missing skill does not exist.
        """
        # TODO: implement
        raise NotImplementedError

    def load(self, name: str) -> str:
        """Return the skill's body and append `name` to self.loaded.

        Unknown name -> SkillError whose message lists the available names, so the
        model can correct a typo on its next turn.
        """
        # TODO: implement
        raise NotImplementedError

    def resources(self, name: str) -> list[str]:
        """Other files in the skill's folder: relative POSIX paths, sorted, recursive,
        excluding SKILL.md. Unknown name -> SkillError. path None -> [].

        This is the third level of progressive disclosure: index line -> SKILL.md
        body -> the scripts and reference files the body mentions.
        """
        # TODO: implement
        raise NotImplementedError


def load_skill_tool(registry: SkillRegistry) -> Tool:
    """Build a Tool named "load_skill" with one required string parameter `name`,
    which returns `registry.load(name)`.

    Easiest: define an inner `def load_skill(name: str) -> str` with a model-facing
    docstring (including an Args: line for name) and return `build_tool(load_skill)`.
    Let SkillError propagate — Tool.call turns it into an error result the model
    can read and recover from.
    """
    # TODO: implement
    raise NotImplementedError
