"""EXERCISE 1 — A todo list the agent keeps in state.

WHY: On a 40-step task the model's plan lives only in its head, which means it lives
nowhere. By step 25 the original request is 30k tokens back and half-forgotten. Give
the agent a `todo_write` tool, keep the list in YOUR state, and show it the current
list on every turn. That one tool is most of why coding agents finish long tasks.

    pytest chapters/ch08b_harness/tests -q -k todos
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from agentlib.llm import LLMResponse, Message
from agentlib.tools import Tool


class TodoStatus(str, Enum):
    """pending -> in_progress -> completed. Subclasses `str`, like StopReason."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoError(ValueError):
    """The model sent a list that breaks the rules. It reaches the model as a tool
    error (Tool.call turns exceptions into error results), so it can fix and retry."""


#: How each status is drawn by `render()`.
MARKS = {
    TodoStatus.PENDING: "[ ]",
    TodoStatus.IN_PROGRESS: "[>]",
    TodoStatus.COMPLETED: "[x]",
}


@dataclass
class Todo:
    """Fields: id: str, content: str, status: TodoStatus = PENDING"""

    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Todo":
        """Build a Todo from what the model sent: {"id", "content", "status"}.

        Spec:
          * not a dict                     -> TodoError
          * "id" missing, None or ""       -> TodoError mentioning 'id'
          * id may be an int: store str(id)
          * content: str(...).strip(); empty after stripping -> TodoError
            mentioning 'content'
          * status defaults to "pending"; anything that is not a TodoStatus value
            -> TodoError mentioning 'status' (and listing the three valid values)
        """
        # TODO: implement
        raise NotImplementedError

    def to_dict(self) -> dict[str, str]:
        """{"id": ..., "content": ..., "status": "<value string>"}"""
        # TODO: implement
        raise NotImplementedError


def validate_todos(todos: list[Todo]) -> None:
    """Raise TodoError if the list breaks a rule. Return None if it is fine.

    Rules:
      * ids are unique            -> else TodoError("duplicate todo id '...'")
      * at most ONE in_progress   -> else TodoError naming the ids, containing the
                                     word 'in_progress'

    Why only one in progress: it forces the model to finish (or explicitly park)
    one thing before starting the next. Agents that mark four things in progress
    at once are agents that finish none of them.
    """
    # TODO: implement
    raise NotImplementedError


class TodoList:
    """The agent's plan, held in your state rather than in its head.

    __init__(self, *, max_items=50)
        self.max_items, self._items: list[Todo] = [], self.version = 0
    """

    def __init__(self, *, max_items: int = 50) -> None:
        # TODO: implement
        raise NotImplementedError

    @property
    def items(self) -> list[Todo]:
        """A COPY of the list, so callers cannot edit your state by accident."""
        # TODO: implement
        raise NotImplementedError

    def write(self, todos: list[dict[str, Any] | Todo] | str) -> str:
        """Replace the WHOLE list. Returns `self.render()`.

        Spec:
          1. a str -> json.loads it (some models double-encode array arguments);
             bad JSON -> TodoError
          2. not a list -> TodoError
          3. more than max_items -> TodoError mentioning the 'limit'
          4. turn each item into a Todo (Todo objects pass through as-is)
          5. validate_todos(...)
          6. only now: replace self._items and bump self.version

        ATOMIC: if any step raises, the old list must be exactly as it was. A plan
        that is half-overwritten by a bad write is worse than either version.

        Why replace the whole list instead of add/update/remove operations? It is
        one tool with one shape, models get it right first time, and every write is
        a complete snapshot you can log and diff.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def current(self) -> Todo | None:
        """The in_progress todo, or None."""
        # TODO: implement
        raise NotImplementedError

    def counts(self) -> dict[str, int]:
        """{"pending": n, "in_progress": n, "completed": n} — all three keys always."""
        # TODO: implement
        raise NotImplementedError

    @property
    def is_done(self) -> bool:
        """True when the list is NON-EMPTY and every item is completed."""
        # TODO: implement
        raise NotImplementedError

    def render(self) -> str:
        """The compact text block that gets re-injected every turn.

        Empty list -> "Todos: (none)"
        Otherwise, exactly:

            Todos: 1/3 completed
            [x] 1: Read the config
            [>] 2: Fix the parser
            [ ] 3: Run the tests

        Header, then one line per item in list order: f"{MARKS[status]} {id}: {content}".
        Lines joined with "\\n", no trailing newline. Keep it compact — it is paid for
        on every single call.
        """
        # TODO: implement
        raise NotImplementedError

    def reminder(self) -> str:
        """`render()` with a one-line instruction on top. (Given — no need to change.)"""
        return (
            "[Current todo list. Keep it up to date with todo_write; "
            "mark items completed as soon as they are done.]\n" + self.render()
        )

    def inject(self, messages: list[Message]) -> list[Message]:
        """Return a NEW list: a copy of `messages` with the reminder appended.

        Spec:
          * copy every message dict (never mutate the caller's list or dicts)
          * empty todo list -> the copy, unchanged
          * otherwise append {"role": "user", "content": self.reminder()} at the END

        Why the end and not the system prompt: recency. Models attend most to the
        start and the end of the window (Chapter 4, §3), and the end is where the
        current step happens. It also leaves the system prompt byte-identical between
        calls, which keeps prompt caching working.
        """
        # TODO: implement
        raise NotImplementedError


#: The JSON Schema for todo_write. Written by hand, because `@tool` cannot express
#: "an array of objects whose status is one of three strings" from a type hint.
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
    """Build the `todo_write` Tool for this list.

    Return `Tool(name="todo_write", description=..., parameters=TODO_SCHEMA, func=...)`
    where func(todos) calls `todo_list.write(todos)` and returns its result.

    Do NOT catch TodoError inside func. `Tool.call` already turns exceptions into an
    error ToolResult ("TodoError: ..."), which is exactly what the model should see.

    Write the description for the model: send the whole list every time, exactly one
    item in_progress, mark items completed as soon as they are done.
    """
    # TODO: implement
    raise NotImplementedError


class TodoReminderClient:
    """Wrap a client so every request carries the current todo list.

    __init__(self, inner, todo_list)
    chat(self, messages, **kwargs) -> self.inner.chat(todo_list.inject(messages), **kwargs)
    __getattr__(self, name)        -> getattr(self.inner, name)   (so .model etc. work)

    This is the "re-inject each turn" trick without touching the Agent loop: the
    Agent hands its messages to `client.chat`, and this wrapper adds the reminder on
    the way out. The reminder is NEVER stored in the conversation, so there is only
    ever one copy of the plan in the window — the current one.
    """

    def __init__(self, inner: Any, todo_list: TodoList) -> None:
        # TODO: implement
        raise NotImplementedError

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        # TODO: implement
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        # TODO: implement
        raise NotImplementedError
