"""Tests for Chapter 14, Exercise 4 — human in the loop."""

import pytest

from chapters.ch14_security.exercises.exercise_4_approval import ApprovalQueue


class TestQueue:
    def test_request_returns_an_index(self):
        q = ApprovalQueue()
        assert q.request("send_email", {"to": "a@b.com"}) == 0
        assert q.request("delete_user", {"id": "1"}) == 1

    def test_pending_grows(self):
        q = ApprovalQueue()
        q.request("a", {})
        q.request("b", {})
        assert len(q.pending) == 2

    def test_stores_the_tool_and_arguments(self):
        q = ApprovalQueue()
        i = q.request("send_email", {"to": "a@b.com"}, "user asked")
        assert q.pending[i].tool == "send_email"
        assert q.pending[i].arguments == {"to": "a@b.com"}
        assert q.pending[i].reason == "user asked"

    def test_arguments_are_copied(self):
        # an approval that changes after it was shown to a human is worse than none
        q = ApprovalQueue()
        arguments = {"to": "a@b.com"}
        i = q.request("send_email", arguments)
        arguments["to"] = "attacker@evil.com"
        assert q.pending[i].arguments["to"] == "a@b.com"


class TestDecisions:
    def test_undecided_is_none_not_false(self):
        # False would auto-deny the moment a human is slow, which looks like a bug
        q = ApprovalQueue()
        i = q.request("send_email", {})
        assert q.approved(i) is None

    def test_approve(self):
        q = ApprovalQueue()
        i = q.request("send_email", {})
        q.resolve(i, True)
        assert q.approved(i) is True

    def test_deny(self):
        q = ApprovalQueue()
        i = q.request("send_email", {})
        q.resolve(i, False)
        assert q.approved(i) is False

    def test_decisions_are_independent(self):
        q = ApprovalQueue()
        a = q.request("one", {})
        b = q.request("two", {})
        q.resolve(a, True)
        assert q.approved(a) is True
        assert q.approved(b) is None


class TestDescribe:
    def test_shows_the_tool_and_arguments(self):
        q = ApprovalQueue()
        i = q.request("send_email", {"to": "a@b.com", "subject": "Closed"})
        out = q.describe(i)
        assert "send_email" in out
        assert "a@b.com" in out
        assert "Closed" in out

    def test_arguments_are_what_makes_it_a_decision(self):
        # "Approve send_email?" is a keypress, not a decision
        q = ApprovalQueue()
        i = q.request("send_email", {"to": "412 recipients"})
        assert "412 recipients" in q.describe(i)

    def test_includes_the_reason_when_there_is_one(self):
        q = ApprovalQueue()
        i = q.request("delete_user", {"id": "1"}, "the user asked to close the account")
        assert "the user asked" in q.describe(i)

    def test_omits_the_reason_line_when_there_is_none(self):
        q = ApprovalQueue()
        i = q.request("delete_user", {"id": "1"})
        assert "reason" not in q.describe(i)

    def test_no_arguments(self):
        q = ApprovalQueue()
        i = q.request("shutdown", {})
        assert "shutdown" in q.describe(i)
