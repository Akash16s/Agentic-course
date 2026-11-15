"""Tests for Chapter 14, Exercise 1 — permissions."""

import pytest

from agentlib.tools import ToolRegistry, tool
from chapters.ch14_security.exercises.exercise_1_permissions import (
    Decision,
    GuardedRegistry,
    PermissionPolicy,
    Rule,
)


@tool
def read_file(path: str) -> str:
    """Read a file."""
    return f"contents of {path}"


@tool
def delete_user(user_id: str) -> str:
    """Delete a user."""
    return f"deleted {user_id}"


@tool
def send_email(to: str) -> str:
    """Send an email."""
    return f"sent to {to}"


REG = ToolRegistry([read_file, delete_user, send_email])


class TestDecision:
    def test_three_decisions(self):
        assert {d.value for d in Decision} == {"allow", "ask", "deny"}


class TestDefaultDeny:
    def test_unknown_tool_is_denied(self):
        # with default-allow, every tool added later ships enabled
        assert PermissionPolicy().decide("anything") is Decision.DENY

    def test_default_is_configurable(self):
        policy = PermissionPolicy(default=Decision.ALLOW)
        assert policy.decide("anything") is Decision.ALLOW


class TestRules:
    def test_exact_name(self):
        policy = PermissionPolicy().allow("read_file")
        assert policy.decide("read_file") is Decision.ALLOW
        assert policy.decide("write_file") is Decision.DENY

    def test_glob(self):
        policy = PermissionPolicy().allow("read_*")
        assert policy.decide("read_file") is Decision.ALLOW
        assert policy.decide("read_directory") is Decision.ALLOW
        assert policy.decide("write_file") is Decision.DENY

    def test_star_matches_everything(self):
        assert PermissionPolicy().allow("*").decide("anything") is Decision.ALLOW

    def test_chaining(self):
        policy = PermissionPolicy().allow("read_*").deny("delete_*").ask("send_*")
        assert policy.decide("read_x") is Decision.ALLOW
        assert policy.decide("delete_x") is Decision.DENY
        assert policy.decide("send_x") is Decision.ASK


class TestOrdering:
    def test_first_match_wins(self):
        policy = PermissionPolicy().deny("read_secrets").allow("read_*")
        assert policy.decide("read_secrets") is Decision.DENY
        assert policy.decide("read_notes") is Decision.ALLOW

    def test_wrong_order_lets_the_exception_through(self):
        # the mistake this ordering rule exists to prevent
        policy = PermissionPolicy().allow("read_*").deny("read_secrets")
        assert policy.decide("read_secrets") is Decision.ALLOW


class TestArgumentPredicates:
    def test_predicate_narrows_a_rule(self):
        policy = (PermissionPolicy()
                  .deny("read_file", when=lambda a: "secret" in str(a.get("path", "")))
                  .allow("read_file"))
        assert policy.decide("read_file", {"path": "notes.md"}) is Decision.ALLOW
        assert policy.decide("read_file", {"path": "secrets.env"}) is Decision.DENY

    def test_predicate_on_recipients(self):
        internal = (PermissionPolicy()
                    .allow("send_email", when=lambda a: a.get("to", "").endswith("@acme.com"))
                    .ask("send_email"))
        assert internal.decide("send_email", {"to": "x@acme.com"}) is Decision.ALLOW
        assert internal.decide("send_email", {"to": "x@elsewhere.com"}) is Decision.ASK

    def test_missing_arguments_do_not_crash(self):
        policy = PermissionPolicy().allow("read_file", when=lambda a: a["path"] == "x")
        assert policy.decide("read_file", {}) is Decision.DENY

    def test_a_raising_predicate_does_not_match(self):
        # a buggy predicate must fall through, not take the agent down
        def explode(arguments):
            raise RuntimeError("bug")

        policy = PermissionPolicy().allow("read_file", when=explode)
        assert policy.decide("read_file", {}) is Decision.DENY

    def test_no_arguments_given(self):
        assert PermissionPolicy().allow("read_*").decide("read_file") is Decision.ALLOW


class TestGuardedRegistry:
    def policy(self):
        return (PermissionPolicy()
                .deny("read_file", when=lambda a: "secret" in str(a.get("path", "")))
                .allow("read_*")
                .ask("send_email")
                .deny("delete_*"))

    def test_allowed_call_goes_through(self):
        guard = GuardedRegistry(REG, self.policy())
        result = guard.execute("read_file", {"path": "notes.md"})
        assert not result.is_error
        assert "notes.md" in result.content

    def test_denial_is_a_tool_result_not_an_exception(self):
        # the model should see this and route around it, like any tool failure
        guard = GuardedRegistry(REG, self.policy())
        result = guard.execute("delete_user", {"user_id": "1"})
        assert result.is_error
        assert "permission denied" in result.content

    def test_denial_by_argument(self):
        guard = GuardedRegistry(REG, self.policy())
        assert guard.execute("read_file", {"path": "secrets.env"}).is_error

    def test_denied_calls_are_recorded(self):
        guard = GuardedRegistry(REG, self.policy())
        guard.execute("delete_user", {"user_id": "1"})
        assert len(guard.denied) == 1
        assert guard.denied[0][0] == "delete_user"

    def test_the_underlying_tool_is_never_reached(self):
        calls = []

        @tool
        def dangerous(x: int) -> str:
            """Should never run."""
            calls.append(x)
            return "ran"

        guard = GuardedRegistry(ToolRegistry([dangerous]), PermissionPolicy())
        guard.execute("dangerous", {"x": 1})
        assert calls == [], "a denied tool must not execute"

    def test_ask_without_an_approver_is_denied(self):
        guard = GuardedRegistry(REG, self.policy())
        assert guard.execute("send_email", {"to": "a@b.com"}).is_error

    def test_ask_with_approval(self):
        guard = GuardedRegistry(REG, self.policy(), approve=lambda t, a: True)
        assert not guard.execute("send_email", {"to": "a@b.com"}).is_error

    def test_ask_with_refusal(self):
        guard = GuardedRegistry(REG, self.policy(), approve=lambda t, a: False)
        result = guard.execute("send_email", {"to": "a@b.com"})
        assert result.is_error
        assert "declined" in result.content

    def test_approver_sees_the_arguments(self):
        seen = []
        guard = GuardedRegistry(REG, self.policy(),
                                approve=lambda t, a: seen.append((t, a)) or True)
        guard.execute("send_email", {"to": "a@b.com"})
        assert seen == [("send_email", {"to": "a@b.com"})]

    def test_delegates_other_attributes(self):
        guard = GuardedRegistry(REG, self.policy())
        assert "read_file" in guard.names
        assert len(guard.specs()) == 3

    def test_json_string_arguments_still_reach_the_registry(self):
        guard = GuardedRegistry(REG, PermissionPolicy().allow("*"))
        result = guard.execute("read_file", '{"path": "notes.md"}')
        assert "notes.md" in result.content
