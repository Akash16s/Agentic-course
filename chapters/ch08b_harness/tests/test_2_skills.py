"""Tests for Chapter 8b, Exercise 2 — skills and progressive disclosure."""

import pytest

from chapters.ch08b_harness.exercises.exercise_2_skills import (
    Skill,
    SkillError,
    SkillRegistry,
    load_skill_tool,
    parse_skill,
)

GOOD = """---
name: pdf-forms
description: Fill in PDF forms. Use when the user gives you a .pdf with fields.
---
# Filling PDF forms

1. List the fields first.
2. Never guess a value.
"""


def make_skill(root, folder, name=None, description="Does a thing.", body="Body text.",
               raw=None, extra_files=()):
    d = root / folder
    d.mkdir(parents=True)
    text = raw if raw is not None else (
        f"---\nname: {name or folder}\ndescription: {description}\n---\n{body}\n"
    )
    (d / "SKILL.md").write_text(text)
    for rel in extra_files:
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text("x")
    return d


class TestParse:
    def test_parses_name_description_and_body(self):
        s = parse_skill(GOOD)
        assert s.name == "pdf-forms"
        assert s.description.startswith("Fill in PDF forms.")
        assert s.body.startswith("# Filling PDF forms")
        assert s.body.endswith("Never guess a value.")

    def test_body_is_stripped(self):
        s = parse_skill("---\nname: a\ndescription: d\n---\n\n\n  hello  \n\n")
        assert s.body == "hello"

    def test_quoted_values_are_unquoted(self):
        s = parse_skill('---\nname: "a"\ndescription: \'Use it: always.\'\n---\nb')
        assert s.name == "a"
        assert s.description == "Use it: always."

    def test_extra_keys_go_to_metadata(self):
        s = parse_skill("---\nname: a\ndescription: d\nversion: 2\n---\nb")
        assert s.metadata == {"version": "2"}

    def test_no_frontmatter(self):
        with pytest.raises(SkillError, match="frontmatter"):
            parse_skill("# Just a heading\nbody")

    def test_unclosed_frontmatter(self):
        with pytest.raises(SkillError, match="closed"):
            parse_skill("---\nname: a\ndescription: d\nbody")

    @pytest.mark.parametrize("missing", ["name", "description"])
    def test_missing_required_field_names_the_field(self, missing):
        fields = {"name": "a", "description": "d"}
        del fields[missing]
        text = "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + "---\nb"
        with pytest.raises(SkillError, match=missing):
            parse_skill(text)

    def test_empty_description_counts_as_missing(self):
        with pytest.raises(SkillError, match="description"):
            parse_skill("---\nname: a\ndescription:\n---\nb")

    def test_line_without_colon(self):
        with pytest.raises(SkillError):
            parse_skill("---\nname: a\ndescription: d\nnonsense\n---\nb")

    @pytest.mark.parametrize("bad", ["PDF Forms", "pdf_forms"])
    def test_bad_names_rejected(self, bad):
        with pytest.raises(SkillError, match="name"):
            parse_skill(f"---\nname: {bad}\ndescription: d\n---\nb")


class TestRegistry:
    def test_discovers_skill_folders(self, tmp_path):
        make_skill(tmp_path, "b-skill")
        make_skill(tmp_path, "a-skill")
        reg = SkillRegistry(tmp_path)
        assert reg.names == ["a-skill", "b-skill"]
        assert len(reg) == 2
        assert "a-skill" in reg

    def test_ignores_files_not_in_a_skill_folder(self, tmp_path):
        (tmp_path / "SKILL.md").write_text(GOOD)            # at the root: not a skill
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "README.md").write_text("x")  # folder without SKILL.md
        assert len(SkillRegistry(tmp_path)) == 0

    def test_uses_the_frontmatter_name_not_the_folder(self, tmp_path):
        make_skill(tmp_path, "folder-x", name="real-name")
        assert SkillRegistry(tmp_path).names == ["real-name"]

    def test_missing_root_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SkillRegistry(tmp_path / "nope")

    def test_one_broken_skill_does_not_break_the_rest(self, tmp_path):
        make_skill(tmp_path, "good")
        make_skill(tmp_path, "broken", raw="no frontmatter here")
        reg = SkillRegistry(tmp_path)
        assert reg.names == ["good"]
        assert "broken" in reg.errors

    def test_duplicate_names_are_reported(self, tmp_path):
        make_skill(tmp_path, "one", name="same")
        make_skill(tmp_path, "two", name="same")
        reg = SkillRegistry(tmp_path)
        assert reg.names == ["same"]
        assert reg.errors and "duplicate" in next(iter(reg.errors.values()))

    def test_load_returns_the_body_and_records_it(self, tmp_path):
        make_skill(tmp_path, "a", body="Step 1. Do it.")
        reg = SkillRegistry(tmp_path)
        assert reg.load("a") == "Step 1. Do it."
        assert reg.loaded == ["a"]

    def test_load_unknown_lists_what_exists(self, tmp_path):
        make_skill(tmp_path, "real")
        with pytest.raises(SkillError, match="real"):
            SkillRegistry(tmp_path).load("imaginary")

    def test_resources_lists_other_files(self, tmp_path):
        make_skill(tmp_path, "a", extra_files=["scripts/fill.py", "reference.md"])
        assert SkillRegistry(tmp_path).resources("a") == ["reference.md", "scripts/fill.py"]


class TestIndexPrompt:
    def test_empty_registry_is_empty_string(self, tmp_path):
        assert SkillRegistry(tmp_path).index_prompt() == ""

    def test_lists_names_and_descriptions_but_not_bodies(self, tmp_path):
        make_skill(tmp_path, "a", description="Use for A.", body="SECRET BODY A")
        make_skill(tmp_path, "b", description="Use for B.", body="SECRET BODY B")
        out = SkillRegistry(tmp_path).index_prompt()
        assert "load_skill" in out
        assert "- a: Use for A." in out and "- b: Use for B." in out
        assert "SECRET BODY" not in out, "bodies load on demand — that is the whole point"

    def test_long_descriptions_are_cut(self, tmp_path):
        make_skill(tmp_path, "a", description="x" * 500)
        out = SkillRegistry(tmp_path).index_prompt(max_description_chars=50)
        line = next(l for l in out.splitlines() if l.startswith("- a:"))
        assert line == "- a: " + "x" * 47 + "..."

    def test_respects_the_budget_and_says_what_it_left_out(self, tmp_path):
        for i in range(30):
            make_skill(tmp_path, f"skill-{i:02d}", description="Does something useful. " * 3)
        out = SkillRegistry(tmp_path).index_prompt(max_chars=600)
        assert len(out) <= 600
        listed = [l for l in out.splitlines() if l.startswith("- ")]
        assert 0 < len(listed) < 30
        assert out.splitlines()[-1] == f"(+{30 - len(listed)} more skills not listed)"

    def test_everything_fits_means_no_overflow_note(self, tmp_path):
        make_skill(tmp_path, "a")
        assert "more skills" not in SkillRegistry(tmp_path).index_prompt()


class TestTool:
    def test_tool_spec(self, tmp_path):
        spec = load_skill_tool(SkillRegistry(tmp_path)).spec()["function"]
        assert spec["name"] == "load_skill"
        assert spec["parameters"]["required"] == ["name"]

    def test_tool_returns_the_body(self, tmp_path):
        make_skill(tmp_path, "a", body="Do it like this.")
        result = load_skill_tool(SkillRegistry(tmp_path)).call({"name": "a"})
        assert not result.is_error
        assert result.content == "Do it like this."

    def test_unknown_skill_is_a_recoverable_tool_error(self, tmp_path):
        make_skill(tmp_path, "real")
        result = load_skill_tool(SkillRegistry(tmp_path)).call({"name": "nope"})
        assert result.is_error
        assert "real" in result.content
