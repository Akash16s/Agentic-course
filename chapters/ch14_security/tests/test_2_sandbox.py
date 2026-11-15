"""Tests for Chapter 14, Exercise 2 — path sandboxing."""

import os

import pytest

from chapters.ch14_security.exercises.exercise_2_sandbox import (
    PathEscape,
    safe_join,
    sandbox_path,
)


@pytest.fixture
def root(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text("hello")
    (tmp_path / "secret.txt").write_text("shh")
    return tmp_path


class TestAllowed:
    def test_simple_file(self, root):
        assert sandbox_path(root, "secret.txt") == (root / "secret.txt").resolve()

    def test_nested(self, root):
        assert sandbox_path(root, "notes/a.md") == (root / "notes" / "a.md").resolve()

    def test_the_root_itself(self, root):
        assert sandbox_path(root, ".") == root.resolve()

    def test_a_path_that_does_not_exist_yet(self, root):
        # writing a new file must be allowed; only ESCAPING is the problem
        assert sandbox_path(root, "notes/new.md")

    def test_harmless_internal_traversal(self, root):
        assert sandbox_path(root, "notes/../secret.txt") == (root / "secret.txt").resolve()


class TestBlocked:
    def test_traversal(self, root):
        with pytest.raises(PathEscape):
            sandbox_path(root, "../../../etc/passwd")

    def test_absolute_path(self, root):
        # Path(root) / "/etc/passwd" is "/etc/passwd": pathlib lets absolute win
        with pytest.raises(PathEscape):
            sandbox_path(root, "/etc/passwd")

    def test_traversal_after_a_legitimate_prefix(self, root):
        with pytest.raises(PathEscape):
            sandbox_path(root, "notes/../../../../etc/passwd")

    def test_parent_directory(self, root):
        with pytest.raises(PathEscape):
            sandbox_path(root, "..")

    def test_sibling_directory_with_a_shared_prefix(self, root, tmp_path):
        # a str.startswith check would wrongly allow this
        sibling = tmp_path.parent / (tmp_path.name + "-backup")
        sibling.mkdir(exist_ok=True)
        with pytest.raises(PathEscape):
            sandbox_path(root, f"../{sibling.name}/x")

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_symlink_pointing_out(self, root, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        link = root / "link.txt"
        link.symlink_to(outside)
        with pytest.raises(PathEscape):
            sandbox_path(root, "link.txt")


class TestSafeJoin:
    def test_returns_a_path_when_allowed(self, root):
        assert safe_join(root, "secret.txt") is not None

    def test_returns_none_when_blocked(self, root):
        assert safe_join(root, "../../../etc/passwd") is None

    def test_does_not_raise(self, root):
        for candidate in ["..", "/etc/passwd", "../../..", "notes/../../.."]:
            safe_join(root, candidate)
