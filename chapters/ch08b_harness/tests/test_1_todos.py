"""Tests for Chapter 8b, Exercise 1 — the todo list."""

import json

import pytest

from agentlib.agent import Agent
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry
from chapters.ch08b_harness.exercises.exercise_1_todos import (
    Todo,
    TodoError,
    TodoList,
    TodoReminderClient,
    TodoStatus,
    todo_write_tool,
    validate_todos,
)


def items(*specs):
    """items(("1", "read", "completed"), ...) -> list of dicts, as a model sends them."""
    return [{"id": i, "content": c, "status": s} for i, c, s in specs]


PLAN = items(
    ("1", "Read the config", "completed"),
    ("2", "Fix the parser", "in_progress"),
    ("3", "Run the tests", "pending"),
)


class TestTodo:
    def test_from_dict(self):
        t = Todo.from_dict({"id": "1", "content": "Read it", "status": "in_progress"})
        assert t == Todo("1", "Read it", TodoStatus.IN_PROGRESS)

    def test_status_defaults_to_pending(self):
        assert Todo.from_dict({"id": "1", "content": "x"}).status is TodoStatus.PENDING

    def test_missing_id_is_an_error(self):
        with pytest.raises(TodoError, match="id"):
            Todo.from_dict({"content": "x"})

    def test_empty_content_is_an_error(self):
        with pytest.raises(TodoError, match="content"):
            Todo.from_dict({"id": "1", "content": "   "})

    def test_unknown_status_is_an_error(self):
        with pytest.raises(TodoError, match="status"):
            Todo.from_dict({"id": "1", "content": "x", "status": "doing"})


class TestValidate:
    def test_valid_list_passes(self):
        validate_todos([Todo.from_dict(d) for d in PLAN])

    def test_duplicate_ids_rejected(self):
        with pytest.raises(TodoError, match="duplicate"):
            validate_todos([Todo("1", "a"), Todo("1", "b")])

    def test_two_in_progress_rejected(self):
        todos = [Todo("1", "a", TodoStatus.IN_PROGRESS), Todo("2", "b", TodoStatus.IN_PROGRESS)]
        with pytest.raises(TodoError, match="in_progress"):
            validate_todos(todos)


class TestTodoList:
    def test_starts_empty(self):
        t = TodoList()
        assert t.items == [] and t.current is None and t.version == 0

    def test_write_replaces_the_whole_list(self):
        t = TodoList()
        t.write(PLAN)
        t.write(items(("9", "Only this", "pending")))
        assert [x.id for x in t.items] == ["9"]

    def test_write_bumps_version(self):
        t = TodoList()
        t.write(PLAN)
        t.write(PLAN)
        assert t.version == 2

    def test_invalid_write_leaves_the_old_list_untouched(self):
        t = TodoList()
        t.write(PLAN)
        with pytest.raises(TodoError):
            t.write(items(("a", "x", "in_progress"), ("b", "y", "in_progress")))
        assert [x.id for x in t.items] == ["1", "2", "3"], "a bad write must change nothing"
        assert t.version == 1

    def test_accepts_a_json_string(self):
        t = TodoList()
        t.write(json.dumps(PLAN))
        assert len(t.items) == 3

    def test_max_items(self):
        with pytest.raises(TodoError, match="limit"):
            TodoList(max_items=2).write(PLAN)

    def test_current_is_the_in_progress_item(self):
        t = TodoList()
        t.write(PLAN)
        assert t.current.id == "2"

    def test_counts(self):
        t = TodoList()
        t.write(PLAN)
        assert t.counts() == {"pending": 1, "in_progress": 1, "completed": 1}

    def test_is_done(self):
        t = TodoList()
        assert not t.is_done, "an empty list is not 'done' — nothing was planned"
        t.write(PLAN)
        assert not t.is_done
        t.write(items(("1", "a", "completed"), ("2", "b", "completed")))
        assert t.is_done


class TestRender:
    def test_empty(self):
        assert TodoList().render() == "Todos: (none)"

    def test_exact_format(self):
        t = TodoList()
        t.write(PLAN)
        assert t.render() == (
            "Todos: 1/3 completed\n"
            "[x] 1: Read the config\n"
            "[>] 2: Fix the parser\n"
            "[ ] 3: Run the tests"
        )


class TestInject:
    def test_appends_the_reminder_as_the_last_user_message(self):
        t = TodoList()
        t.write(PLAN)
        out = t.inject([{"role": "system", "content": "s"}, {"role": "user", "content": "go"}])
        assert len(out) == 3
        assert out[-1]["role"] == "user"
        assert t.render() in out[-1]["content"]
        assert out[-1]["content"] == t.reminder()

    def test_does_not_mutate_the_input(self):
        t = TodoList()
        t.write(PLAN)
        messages = [{"role": "user", "content": "go"}]
        t.inject(messages)
        assert messages == [{"role": "user", "content": "go"}]

    def test_empty_list_injects_nothing(self):
        messages = [{"role": "user", "content": "go"}]
        assert TodoList().inject(messages) == messages


class TestTool:
    def test_name_and_schema(self):
        spec = todo_write_tool(TodoList()).spec()["function"]
        assert spec["name"] == "todo_write"
        item = spec["parameters"]["properties"]["todos"]["items"]
        assert item["properties"]["status"]["enum"] == ["pending", "in_progress", "completed"]
        assert spec["parameters"]["required"] == ["todos"]

    def test_call_writes_the_list(self):
        t = TodoList()
        result = todo_write_tool(t).call({"todos": PLAN})
        assert not result.is_error
        assert result.content == t.render()

    def test_invalid_call_comes_back_as_a_tool_error(self):
        t = TodoList()
        bad = items(("a", "x", "in_progress"), ("b", "y", "in_progress"))
        result = todo_write_tool(t).call({"todos": bad})
        assert result.is_error, "the model must see the error so it can fix the list"
        assert "in_progress" in result.content
        assert t.items == []


class TestReminderClient:
    def test_wraps_chat_and_injects(self):
        t = TodoList()
        t.write(PLAN)
        inner = FakeLLMClient(["ok"])
        TodoReminderClient(inner, t).chat([{"role": "user", "content": "go"}], max_tokens=5)
        sent, kwargs = inner.calls[0]
        assert sent[-1]["content"] == t.reminder()
        assert kwargs["max_tokens"] == 5

    def test_forwards_other_attributes(self):
        inner = FakeLLMClient(model="fake/x")
        assert TodoReminderClient(inner, TodoList()).model == "fake/x"

    def test_in_an_agent_the_plan_is_reinjected_but_never_stored(self):
        t = TodoList()
        inner = FakeLLMClient([
            tool_response(tool_call("todo_write", {"todos": PLAN})),
            "All done.",
        ])
        agent = Agent(TodoReminderClient(inner, t), tools=ToolRegistry([todo_write_tool(t)]))
        result = agent.run("fix the parser")
        assert result.output == "All done."
        # 1st request: list was empty, so no reminder
        assert inner.calls[0][0][-1]["content"] == "fix the parser"
        # 2nd request: the reminder is the last message
        assert inner.calls[1][0][-1]["content"] == t.reminder()
        # ...but the stored conversation never accumulates copies of it
        assert all(m.get("content") != t.reminder() for m in result.conversation.messages)
