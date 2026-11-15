"""SOLUTION — Chapter 8b, Exercise 2."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from agentlib.tools import Tool, build_tool


class SkillError(ValueError):
    pass


SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

INDEX_HEADER = (
    "Skills you can load. Each line is `name: when to use it`. Before starting a task "
    "a skill covers, call load_skill(name) to read its full instructions."
)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def parse_skill(text: str, *, path: Path | None = None) -> Skill:
    lines = text.lstrip("﻿").lstrip().splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("missing frontmatter: the file must start with a '---' line")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise SkillError("frontmatter is never closed with a '---' line") from None

    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise SkillError(f"bad frontmatter line {line.strip()!r}: expected 'key: value'")
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        meta[key.strip()] = value

    for required in ("name", "description"):
        if not meta.get(required):
            raise SkillError(f"frontmatter is missing {required!r}")
    name = meta.pop("name")
    if not SKILL_NAME.match(name):
        raise SkillError(
            f"bad skill name {name!r}: use lowercase letters, digits and hyphens"
        )
    description = meta.pop("description")
    body = "\n".join(lines[end + 1:]).strip()
    return Skill(name=name, description=description, body=body, path=path, metadata=meta)


class SkillRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"skills directory {str(self.root)!r} does not exist")
        self._skills: dict[str, Skill] = {}
        self.errors: dict[str, str] = {}
        self.loaded: list[str] = []
        for skill_file in sorted(self.root.glob("*/SKILL.md")):
            folder = skill_file.parent.name
            try:
                skill = parse_skill(skill_file.read_text(encoding="utf-8"),
                                    path=skill_file.parent)
            except SkillError as exc:
                self.errors[folder] = str(exc)
                continue
            if skill.name in self._skills:
                self.errors[folder] = f"duplicate skill name {skill.name!r}"
                continue
            self._skills[skill.name] = skill

    @property
    def names(self) -> list[str]:
        return sorted(self._skills)

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: object) -> bool:
        return name in self._skills

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def index_prompt(self, *, max_chars: int = 2000, max_description_chars: int = 200) -> str:
        if not self._skills:
            return ""
        skills = [self._skills[n] for n in self.names]
        lines = [INDEX_HEADER]
        for i, skill in enumerate(skills):
            desc = skill.description
            if len(desc) > max_description_chars:
                desc = desc[: max_description_chars - 3] + "..."
            line = f"- {skill.name}: {desc}"
            remaining = len(skills) - i - 1
            reserve = [f"(+{remaining} more skills not listed)"] if remaining else []
            if len("\n".join(lines + [line] + reserve)) > max_chars:
                lines.append(f"(+{len(skills) - i} more skills not listed)")
                break
            lines.append(line)
        return "\n".join(lines)

    def load(self, name: str) -> str:
        skill = self._skills.get(name)
        if skill is None:
            raise SkillError(
                f"unknown skill {name!r}. Available: {', '.join(self.names) or 'none'}"
            )
        self.loaded.append(name)
        return skill.body

    def resources(self, name: str) -> list[str]:
        skill = self._skills.get(name)
        if skill is None:
            raise SkillError(f"unknown skill {name!r}")
        if skill.path is None:
            return []
        return sorted(
            p.relative_to(skill.path).as_posix()
            for p in skill.path.rglob("*")
            if p.is_file() and p.name != "SKILL.md"
        )


def load_skill_tool(registry: SkillRegistry) -> Tool:
    def load_skill(name: str) -> str:
        """Load the full instructions for a skill. Call this before doing a task the
        skill covers.

        Args:
            name: the skill name, exactly as listed in the system prompt
        """
        return registry.load(name)

    return build_tool(load_skill)
