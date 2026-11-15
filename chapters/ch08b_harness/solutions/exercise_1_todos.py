"""SOLUTION — Chapter 8b, Exercise 1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from agentlib.llm import LLMResponse, Message
from agentlib.tools import Tool


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoError(ValueError):
    pass


MARKS = {
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
    def __init__(self, *, max_items: int = 50) -> None:
        self.max_items = max_items
        self._items: list[Todo] = []
        self.version = 0

    @property
    def items(self) -> list[Todo]:
        return list(self._items)

    def write(self, todos: list[dict[str, Any] | Todo] | str) -> str:
        if isinstance(todos, str):
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
        self._items = parsed
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
        lines += [f"{MARKS[t.status]} {t.id}: {t.content}" for t in self._items]
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
    def __init__(self, inner: Any, todo_list: TodoList) -> None:
        self.inner = inner
        self.todo_list = todo_list

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        return self.inner.chat(self.todo_list.inject(messages), **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)
