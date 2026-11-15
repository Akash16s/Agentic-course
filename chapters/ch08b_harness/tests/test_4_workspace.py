"""Tests for Chapter 8b, Exercise 4 — the filesystem as memory."""

import pytest

from agentlib.security import PathEscape
from agentlib.tools import ToolRegistry, tool
from chapters.ch08b_harness.exercises.exercise_4_workspace import (
    Workspace,
    offload_large_output,
    offloading_tool,
)


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path / "ws")


class TestPaths:
    def test_creates_the_root(self, tmp_path):
        Workspace(tmp_path / "a" / "b")
        assert (tmp_path / "a" / "b").is_dir()

    def test_path_inside_is_fine(self, ws):
        assert ws.path("notes/plan.md") == (ws.root / "notes" / "plan.md").resolve()

    @pytest.mark.parametrize("evil", [
        "../escape.txt",
        "/etc/passwd",
        "notes/../../escape.txt",
    ])
    def test_escapes_are_refused(self, ws, evil):
        with pytest.raises(PathEscape):
            ws.path(evil)

    def test_the_root_itself_is_not_a_note(self, ws):
        with pytest.raises(ValueError):
            ws.path(".")


class TestWriteRead:
    def test_round_trip(self, ws):
        assert ws.write_note("plan.md", "step 1") == "wrote 6 chars to plan.md"
        assert ws.read_note("plan.md") == "step 1"

    def test_creates_subdirectories(self, ws):
        ws.write_note("notes/day1/log.md", "hi")
        assert ws.read_note("notes/day1/log.md") == "hi"

    def test_append(self, ws):
        ws.write_note("log.md", "a\n")
        assert ws.write_note("log.md", "b\n", append=True) == "appended 2 chars to log.md"
        assert ws.read_note("log.md") == "a\nb\n"

    def test_note_size_limit(self, tmp_path):
        small = Workspace(tmp_path, max_note_chars=10)
        with pytest.raises(ValueError, match="limit"):
            small.write_note("a.md", "x" * 11)

    def test_missing_note(self, ws):
        with pytest.raises(FileNotFoundError, match="nope.md"):
            ws.read_note("nope.md")

    def test_long_reads_are_chunked_with_a_continue_hint(self, tmp_path):
        w = Workspace(tmp_path, max_read_chars=100)
        w.write_note("big.txt", "x" * 250)
        first = w.read_note("big.txt")
        assert first.startswith("x" * 100)
        assert "offset=100" in first
        assert "of 250" in first

    def test_offset_continues_where_the_hint_said(self, tmp_path):
        w = Workspace(tmp_path, max_read_chars=100)
        w.write_note("abc.txt", "a" * 100 + "b" * 100 + "c" * 50)
        assert w.read_note("abc.txt", offset=100).startswith("b" * 100)
        assert w.read_note("abc.txt", offset=200) == "c" * 50, "last chunk: no hint"


class TestListGrep:
    def test_list_is_sorted_relative_and_recursive(self, ws):
        ws.write_note("b.md", "1")
        ws.write_note("a/z.md", "2")
        ws.write_note("a.md", "3")
        assert ws.list_notes() == ["a.md", "a/z.md", "b.md"]

    def test_grep_reports_file_line_and_text(self, ws):
        ws.write_note("notes.md", "alpha\nThe answer is 42\ngamma\n")
        assert ws.grep_notes("answer") == ["notes.md:2: The answer is 42"]

    def test_grep_is_case_insensitive_by_default(self, ws):
        ws.write_note("a.md", "ERROR here")
        assert len(ws.grep_notes("error")) == 1
        assert ws.grep_notes("error", ignore_case=False) == []

    def test_grep_caps_matches(self, ws):
        ws.write_note("a.md", "hit\n" * 100)
        assert len(ws.grep_notes("hit", max_matches=5)) == 5

    def test_grep_bad_regex_is_a_value_error(self, ws):
        with pytest.raises(ValueError, match="pattern"):
            ws.grep_notes("([unclosed")


class TestTools:
    def test_four_tools(self, ws):
        assert [t.name for t in ws.tools()] == [
            "write_note", "read_note", "list_notes", "grep_notes",
        ]

    def test_tools_work_through_a_registry(self, ws):
        reg = ToolRegistry(ws.tools())
        reg.execute("write_note", {"name": "f.md", "content": "found it: 7"})
        assert reg.execute("read_note", {"name": "f.md"}).content == "found it: 7"
        assert reg.execute("list_notes", {}).content == "f.md"
        assert reg.execute("grep_notes", {"pattern": "found"}).content == "f.md:1: found it: 7"

    def test_empty_results_are_said_out_loud(self, ws):
        reg = ToolRegistry(ws.tools())
        assert reg.execute("list_notes", {}).content == "(workspace is empty)"
        assert reg.execute("grep_notes", {"pattern": "x"}).content == "(no matches)"

    def test_escape_via_a_tool_is_an_error_result(self, ws):
        result = ToolRegistry(ws.tools()).execute("read_note", {"name": "../../etc/passwd"})
        assert result.is_error
        assert "escapes" in result.content


class TestOffload:
    def test_small_output_passes_through_untouched(self, ws):
        assert offload_large_output("short", ws, limit=100) == "short"
        assert ws.list_notes() == []

    def test_large_output_goes_to_a_file(self, ws):
        text = "\n".join(f"row {i}" for i in range(5_000))
        out = offload_large_output(text, ws, limit=1_000, preview_chars=200)
        assert ws.list_notes() == ["outputs/output-001.txt"]
        assert (ws.root / "outputs" / "output-001.txt").read_text() == text
        assert "outputs/output-001.txt" in out
        assert f"{len(text):,} chars" in out
        assert text[:200] in out
        assert len(out) < 600, "the pointer must be far smaller than the output"

    def test_files_are_numbered_and_never_overwritten(self, ws):
        offload_large_output("a" * 50, ws, limit=10)
        offload_large_output("b" * 50, ws, limit=10)
        assert ws.list_notes() == ["outputs/output-001.txt", "outputs/output-002.txt"]

    def test_prefix(self, ws):
        offload_large_output("a" * 50, ws, limit=10, prefix="search")
        assert ws.list_notes() == ["outputs/search-001.txt"]

    def test_offloading_tool_wraps_any_tool(self, ws):
        @tool
        def dump(n: int) -> str:
            """Dump n lines."""
            return "line\n" * n

        wrapped = offloading_tool(dump, ws, limit=100, preview_chars=20)
        assert wrapped.name == "dump" and wrapped.parameters == dump.parameters
        assert wrapped.call({"n": 3}).content == "line\n" * 3
        big = wrapped.call({"n": 1_000}).content
        assert "outputs/dump-001.txt" in big
        assert len(big) < 400

    def test_offloading_tool_stringifies_non_strings(self, ws):
        @tool
        def numbers() -> list:
            """Lots of numbers."""
            return list(range(1_000))

        out = offloading_tool(numbers, ws, limit=50).call({}).content
        assert "outputs/numbers-001.txt" in out
        assert (ws.root / "outputs" / "numbers-001.txt").read_text().startswith("[0, 1, 2")
