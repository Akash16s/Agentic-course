"""Harness patterns — what long-running agents add on top of the loop.

Promoted from Chapter 8b.

The model is the engine; the harness is everything around it: the tools it gets, what
goes into its context each turn, and how the work is split up. Same model, different
harness, very different agent. Four pieces live here:

    TodoList          an explicit plan the agent keeps in state, re-injected each turn
    SkillRegistry     progressive disclosure: names in the prompt, bodies on demand
    SubagentRunner    delegate a task to a child loop with a fresh, isolated context
    Workspace         the filesystem as memory, plus offloading big tool outputs
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from agentlib.agent import Agent, AgentResult
from agentlib.context import middle_out
from agentlib.llm import LLMResponse, Message
from agentlib.security import sandbox_path
from agentlib.tools import Tool, ToolRegistry, build_tool

# ===================================================================== todos


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoError(ValueError):
    """The model sent a todo list that breaks the rules. Comes back to it as a tool
    error, so it can fix the list and try again."""


_MARKS = {
    TodoStatus.PENDING: "[ ]",
    TodoStatus.IN_PROGRESS: "[>]",
    TodoStatus.COMPLETED: "[x]",
}


@dataclass
class Todo:
    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Todo":
        if not isinstance(data, dict):
            raise TodoError(f"each todo must be an object, got {type(data).__name__}")
        if data.get("id") in (None, ""):
            raise TodoError("every todo needs an 'id'")
        content = str(data.get("content") or "").strip()
        if not content:
            raise TodoError(f"todo {data['id']!r} has no 'content'")
        raw_status = data.get("status", "pending")
        try:
            status = TodoStatus(raw_status)
        except ValueError:
            raise TodoError(
                f"invalid status {raw_status!r}; use pending, in_progress or completed"
            ) from None
        return cls(id=str(data["id"]), content=content, status=status)

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "content": self.content, "status": self.status.value}


def validate_todos(todos: list[Todo]) -> None:
    """Unique ids, and at most ONE item in progress."""
    seen: set[str] = set()
    for todo in todos:
        if todo.id in seen:
            raise TodoError(f"duplicate todo id {todo.id!r}")
        seen.add(todo.id)
    active = [t.id for t in todos if t.status is TodoStatus.IN_PROGRESS]
    if len(active) > 1:
        raise TodoError(
            f"{len(active)} todos are in_progress ({', '.join(active)}); "
            "only one may be in progress at a time"
        )


class TodoList:
    """The agent's plan, held in YOUR state rather than in its head.

    The model rewrites the whole list with one tool call (`todo_write`). Whole-list
    replacement is simpler for the model than add/update/delete operations, and it
    makes every write a complete snapshot you can log.
    """

    def __init__(self, *, max_items: int = 50) -> None:
        self.max_items = max_items
        self._items: list[Todo] = []
        self.version = 0

    @property
    def items(self) -> list[Todo]:
        return list(self._items)

    def write(self, todos: list[dict[str, Any] | Todo] | str) -> str:
        if isinstance(todos, str):  # some models double-encode array arguments
            try:
                todos = json.loads(todos)
            except json.JSONDecodeError as exc:
                raise TodoError(f"todos was a string but not valid JSON: {exc}") from None
        if not isinstance(todos, list):
            raise TodoError("todos must be a list")
        if len(todos) > self.max_items:
            raise TodoError(f"too many todos ({len(todos)}); the limit is {self.max_items}")
        parsed = [t if isinstance(t, Todo) else Todo.from_dict(t) for t in todos]
        validate_todos(parsed)
        self._items = parsed          # only replace once the whole list is valid
        self.version += 1
        return self.render()

    @property
    def current(self) -> Todo | None:
        for todo in self._items:
            if todo.status is TodoStatus.IN_PROGRESS:
                return todo
        return None

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in TodoStatus}
        for todo in self._items:
            out[todo.status.value] += 1
        return out

    @property
    def is_done(self) -> bool:
        return bool(self._items) and all(
            t.status is TodoStatus.COMPLETED for t in self._items
        )

    def render(self) -> str:
        if not self._items:
            return "Todos: (none)"
        done = self.counts()["completed"]
        lines = [f"Todos: {done}/{len(self._items)} completed"]
        lines += [f"{_MARKS[t.status]} {t.id}: {t.content}" for t in self._items]
        return "\n".join(lines)

    def reminder(self) -> str:
        return (
            "[Current todo list. Keep it up to date with todo_write; "
            "mark items completed as soon as they are done.]\n" + self.render()
        )

    def inject(self, messages: list[Message]) -> list[Message]:
        out = [dict(m) for m in messages]
        if self._items:
            out.append({"role": "user", "content": self.reminder()})
        return out


TODO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "description": "The COMPLETE list. It replaces the previous one.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "content": {"type": "string", "description": "What to do"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                    },
                },
                "required": ["id", "content", "status"],
            },
        }
    },
    "required": ["todos"],
}


def todo_write_tool(todo_list: TodoList) -> Tool:
    def run(todos: Any) -> str:
        return todo_list.write(todos)

    return Tool(
        name="todo_write",
        description=(
            "Create or update your todo list for multi-step tasks. Send the WHOLE "
            "list every time. Mark exactly one item in_progress while you work on "
            "it, and mark it completed as soon as it is done."
        ),
        parameters=TODO_SCHEMA,
        func=run,
    )


class TodoReminderClient:
    """Wraps a client so every request carries the current todo list at the end.

    The reminder is added at REQUEST time and never stored in the conversation, so
    there is only ever one copy of the plan in the window — the current one.
    """

    def __init__(self, inner: Any, todo_list: TodoList) -> None:
        self.inner = inner
        self.todo_list = todo_list

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        return self.inner.chat(self.todo_list.inject(messages), **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


# ==================================================================== skills


class SkillError(ValueError):
    """A SKILL.md that cannot be used, or a request for a skill that does not exist."""


_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def parse_skill(text: str, *, path: Path | None = None) -> Skill:
    """Parse a SKILL.md: `---` frontmatter of `key: value` lines, then a body."""
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
    if not _SKILL_NAME.match(name):
        raise SkillError(
            f"bad skill name {name!r}: use lowercase letters, digits and hyphens"
        )
    description = meta.pop("description")
    body = "\n".join(lines[end + 1:]).strip()
    return Skill(name=name, description=description, body=body, path=path, metadata=meta)


INDEX_HEADER = (
    "Skills you can load. Each line is `name: when to use it`. Before starting a task "
    "a skill covers, call load_skill(name) to read its full instructions."
)


class SkillRegistry:
    """Discover `<root>/<folder>/SKILL.md` files. Index cheap, load on demand."""

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


# ================================================================= subagents

SUBAGENT_SYSTEM = (
    "You are a subagent. Another agent has given you one self-contained task. Do it "
    "with your tools, then reply with a short final answer: the result and the key "
    "evidence, no preamble. Your final message is the ONLY thing the other agent sees."
)


@dataclass
class SubagentResult:
    task: str
    output: str
    stop_reason: str
    steps: int = 0
    tokens: int = 0
    cost: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.stop_reason in ("done", "stop_tool")


def condense(result: AgentResult, max_chars: int) -> str:
    """What the parent gets to see of a child's whole run."""
    text = (result.output or "").strip() or "(the subagent produced no output)"
    text = middle_out(text, max_chars)
    if not result.succeeded:
        text = f"[subagent stopped early: {result.stop_reason.value}] {text}"
    return text


class SubagentRunner:
    """Run a task in a child agent with a FRESH conversation and restricted tools."""

    def __init__(
        self,
        client: Any,
        tools: ToolRegistry,
        *,
        system: str = SUBAGENT_SYSTEM,
        model: str | None = None,
        max_steps: int = 8,
        max_result_chars: int = 2000,
        max_depth: int = 1,
        depth: int = 0,
        budget_usd: float | None = None,
        on_result: Callable[[SubagentResult], None] | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.system = system
        self.model = model
        self.max_steps = max_steps
        self.max_result_chars = max_result_chars
        self.max_depth = max_depth
        self.depth = depth
        self.budget_usd = budget_usd
        self.on_result = on_result
        self.results: list[SubagentResult] = []

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self.results)

    def restrict(self, names: list[str] | None) -> ToolRegistry:
        wanted = [n for n in self.tools.names if n != "delegate"] if names is None \
            else [n for n in names if n != "delegate"]
        unknown = [n for n in wanted if n not in self.tools]
        if unknown:
            raise ValueError(
                f"unknown tools {unknown}. Available: {', '.join(self.tools.names)}"
            )
        registry = ToolRegistry([self.tools.get(n) for n in dict.fromkeys(wanted)])
        if self.depth + 1 < self.max_depth:
            child = SubagentRunner(
                self.client, self.tools, system=self.system, model=self.model,
                max_steps=self.max_steps, max_result_chars=self.max_result_chars,
                max_depth=self.max_depth, depth=self.depth + 1,
                budget_usd=self.budget_usd, on_result=self._record,
            )
            registry.register(child.as_tool())
        return registry

    def run(self, task: str, tools: list[str] | None = None) -> SubagentResult:
        if self.depth >= self.max_depth:
            return self._record(SubagentResult(
                task, "error: maximum delegation depth reached; do the task yourself",
                stop_reason="error", error="max depth"))
        try:
            registry = self.restrict(tools)
        except ValueError as exc:
            return self._record(SubagentResult(task, f"error: {exc}",
                                               stop_reason="error", error=str(exc)))
        child = Agent(
            self.client, tools=registry, system=self.system, model=self.model,
            max_steps=self.max_steps, budget_usd=self.budget_usd,
        )
        try:
            result = child.run(task)          # a str -> a brand-new conversation
        except Exception as exc:  # noqa: BLE001 - a child must never kill its parent
            msg = f"{type(exc).__name__}: {exc}"
            return self._record(SubagentResult(task, f"error: {msg}",
                                               stop_reason="error", error=msg))
        return self._record(SubagentResult(
            task=task,
            output=condense(result, self.max_result_chars),
            stop_reason=result.stop_reason.value,
            steps=result.step_count,
            tokens=result.usage.total_tokens,
            cost=result.cost,
            error=result.error,
        ))

    def _record(self, result: SubagentResult) -> SubagentResult:
        self.results.append(result)
        if self.on_result is not None:
            self.on_result(result)
        return result

    def as_tool(self) -> Tool:
        available = [n for n in self.tools.names if n != "delegate"]

        def delegate(task: str, tools: list[str] | None = None) -> str:
            """Delegate a self-contained task.

            Args:
                task: everything the subagent needs to know; it sees nothing else
                tools: names of the tools it may use (omit for all)
            """
            return self.run(task, tools).output

        return build_tool(delegate, description=(
            "Delegate a self-contained subtask to a subagent with a fresh, empty "
            "context. It sees ONLY the task text you write, so include every detail "
            "it needs. You get back its final answer, not its working. Use it for "
            "searches and reads that would otherwise flood your context. "
            f"Tools a subagent can use: {', '.join(available) or 'none'}."
        ))


# ================================================================= workspace


class Workspace:
    """A sandboxed directory the agent uses as memory: notes, plans, big outputs."""

    def __init__(self, root: str | Path, *, max_read_chars: int = 4000,
                 max_note_chars: int = 100_000) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_read_chars = max_read_chars
        self.max_note_chars = max_note_chars

    def path(self, name: str) -> Path:
        target = sandbox_path(self.root, name)   # raises PathEscape
        if target == self.root.resolve():
            raise ValueError("a note name must be a file path, not the workspace root")
        return target

    def write_note(self, name: str, content: str, append: bool = False) -> str:
        if len(content) > self.max_note_chars:
            raise ValueError(
                f"note is {len(content)} chars; the limit is {self.max_note_chars}"
            )
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a" if append else "w", encoding="utf-8") as f:
            f.write(content)
        return f"{'appended' if append else 'wrote'} {len(content)} chars to {name}"

    def read_note(self, name: str, offset: int = 0, limit: int | None = None) -> str:
        target = self.path(name)
        if not target.is_file():
            raise FileNotFoundError(f"no note named {name!r}")
        text = target.read_text(encoding="utf-8")
        limit = self.max_read_chars if limit is None else min(limit, self.max_read_chars)
        offset = max(0, offset)
        chunk = text[offset: offset + limit]
        end = offset + len(chunk)
        if end < len(text):
            chunk += (f"\n...[showing chars {offset}-{end} of {len(text)}; "
                      f"call read_note with offset={end} to continue]")
        return chunk

    def list_notes(self) -> list[str]:
        root = self.root.resolve()
        return sorted(
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        )

    def grep_notes(self, pattern: str, *, ignore_case: bool = True,
                   max_matches: int = 50) -> list[str]:
        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            raise ValueError(f"invalid pattern {pattern!r}: {exc}") from None
        out: list[str] = []
        for name in self.list_notes():
            text = (self.root.resolve() / name).read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    out.append(f"{name}:{lineno}: {line.strip()[:200]}")
                    if len(out) >= max_matches:
                        return out
        return out

    def tools(self) -> list[Tool]:
        def write_note(name: str, content: str, append: bool = False) -> str:
            """Save text to a file in your workspace (notes, plans, findings).

            Args:
                name: relative path such as notes/findings.md
                content: the text to write
                append: add to the end instead of replacing the file
            """
            return self.write_note(name, content, append)

        def read_note(name: str, offset: int = 0) -> str:
            """Read a file from your workspace, a chunk at a time.

            Args:
                name: relative path of the file
                offset: character to start from, for reading long files in pieces
            """
            return self.read_note(name, offset)

        def list_notes() -> str:
            """List every file in your workspace."""
            return "\n".join(self.list_notes()) or "(workspace is empty)"

        def grep_notes(pattern: str) -> str:
            """Search every workspace file for a regex. Returns file:line: text.

            Args:
                pattern: a regular expression, matched case-insensitively
            """
            return "\n".join(self.grep_notes(pattern)) or "(no matches)"

        return [build_tool(f) for f in (write_note, read_note, list_notes, grep_notes)]


_PREFIX = re.compile(r"^[A-Za-z0-9_-]+$")


def offload_large_output(text: str, workspace: Workspace, limit: int = 2000, *,
                         preview_chars: int = 500, prefix: str = "output") -> str:
    """Small text passes through. Big text goes to a file; the model gets a pointer."""
    if len(text) <= limit:
        return text
    if not _PREFIX.match(prefix):
        raise ValueError(f"bad prefix {prefix!r}")
    n = 1
    while workspace.path(f"outputs/{prefix}-{n:03d}.txt").exists():
        n += 1
    name = f"outputs/{prefix}-{n:03d}.txt"
    target = workspace.path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    lines = text.count("\n") + 1
    return (
        f"[output too large: {len(text):,} chars, {lines:,} lines. "
        f"Full text saved to {name}]\n"
        f"--- first {preview_chars} chars ---\n"
        f"{text[:preview_chars]}\n"
        f"--- end of preview ---\n"
        f"Use read_note({name!r}, offset=...) or grep_notes(pattern) to see more."
    )


def offloading_tool(tool: Tool, workspace: Workspace, limit: int = 2000, *,
                    preview_chars: int = 500) -> Tool:
    """The same tool, except big results land on disk instead of in the context."""

    def run(**kwargs: Any) -> str:
        value = tool.func(**kwargs)
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        return offload_large_output(text, workspace, limit,
                                    preview_chars=preview_chars, prefix=tool.name)

    return Tool(name=tool.name, description=tool.description,
                parameters=tool.parameters, func=run)
