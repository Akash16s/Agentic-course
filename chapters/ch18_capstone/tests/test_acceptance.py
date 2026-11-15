"""Capstone acceptance suite.

These tests check STRUCTURE — that the required pieces exist and connect. They
cannot tell you whether your agent is any good; that is what your own evals are
for, and building them is most of the point.

Point it at your capstone:

    CAPSTONE_PATH=~/Desktop/Learning/capstone pytest chapters/ch18_capstone/tests -q

With no CAPSTONE_PATH set, everything is skipped, so the course suite stays green
before you start.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

CAPSTONE_PATH = os.getenv("CAPSTONE_PATH")

pytestmark = pytest.mark.skipif(
    not CAPSTONE_PATH,
    reason="set CAPSTONE_PATH to your capstone directory to run the acceptance suite",
)


@pytest.fixture(scope="module")
def root() -> Path:
    path = Path(os.path.expanduser(CAPSTONE_PATH or ".")).resolve()
    if not path.is_dir():
        pytest.fail(f"CAPSTONE_PATH does not exist: {path}")
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return path


def load(root: Path, name: str):
    """Import a module from the capstone directory, or fail with a clear message."""
    path = root / f"{name}.py"
    if not path.exists():
        pytest.fail(f"missing {name}.py — see the starter")
    spec = importlib.util.spec_from_file_location(f"capstone_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source(root: Path, *names: str) -> str:
    """Concatenated source of the named files, for structural checks."""
    text = []
    for name in names:
        path = root / name
        if path.exists():
            text.append(path.read_text(encoding="utf-8"))
    return "\n".join(text)


# ------------------------------------------------------------------- layout


class TestDeliverables:
    @pytest.mark.parametrize("name", [
        "README.md", "DECISIONS.md", "RESULTS.md",
        "agent.py", "service.py", "mcp_server.py",
        "evals/dataset.jsonl", "evals/checks.py", "evals/run.py",
    ])
    def test_file_exists(self, root, name):
        assert (root / name).exists(), f"missing {name}"

    def test_decisions_is_written(self, root):
        text = (root / "DECISIONS.md").read_text()
        assert text.count("TODO") <= 1, "DECISIONS.md is still the template"
        assert len(text) > 800, "requirements 7, 8 and 17 each need a real paragraph"

    def test_results_has_numbers(self, root):
        text = (root / "RESULTS.md").read_text()
        assert "TODO" not in text, "RESULTS.md is still the template"
        assert any(ch.isdigit() for ch in text), "RESULTS.md needs numbers"

    def test_results_records_a_regression(self, root):
        # a results file with no regression means you did not look hard enough
        text = (root / "RESULTS.md").read_text().lower()
        assert "worse" in text or "regress" in text, (
            "RESULTS.md must record something that got worse"
        )


# --------------------------------------------------------------- the agent


class TestAgent:
    def test_imports(self, root):
        load(root, "agent")

    def test_exposes_run(self, root):
        agent = load(root, "agent")
        assert callable(getattr(agent, "run", None)), "agent.run(task) is required"

    def test_has_a_system_prompt(self, root):
        agent = load(root, "agent")
        prompt = getattr(agent, "SYSTEM_PROMPT", "")
        assert prompt and "TODO" not in prompt, "write a real system prompt"

    def test_builds_a_registry(self, root):
        agent = load(root, "agent")
        builder = getattr(agent, "build_agent", None)
        assert callable(builder), "build_agent() is required"

    def test_at_least_four_tools(self, root):
        from agentlib.tools import Tool

        agent = load(root, "agent")
        tools = [v for v in vars(agent).values() if isinstance(v, Tool)]
        assert len(tools) >= 4, f"requirement 2: found {len(tools)} tools, need 4"

    def test_tools_have_descriptions(self, root):
        from agentlib.tools import Tool

        agent = load(root, "agent")
        for t in [v for v in vars(agent).values() if isinstance(v, Tool)]:
            assert t.description and t.description != t.name, (
                f"tool {t.name!r} has no real description (ch 2)"
            )

    def test_tools_document_their_parameters(self, root):
        from agentlib.tools import Tool

        agent = load(root, "agent")
        for t in [v for v in vars(agent).values() if isinstance(v, Tool)]:
            for name, schema in t.parameters.get("properties", {}).items():
                assert schema.get("description"), (
                    f"{t.name}.{name} has no description (ch 2, §4)"
                )


class TestWiring:
    """Each check looks for the chapter's machinery actually being imported."""

    def src(self, root):
        return source(root, "agent.py", "service.py")

    @pytest.mark.parametrize("requirement,needles", [
        ("1  retries + cost",      ["chat_with_retry", "CostTracker", "retry"]),
        ("3  the agent loop",      ["Agent(", "StopReason"]),
        ("4  bounded tool output", ["truncate_tool_results", "middle_out",
                                    "ContextBudget", "max_chars"]),
        ("5  durable sessions",    ["SQLiteSessionStore", "SessionStore"]),
        ("6  long-term memory",    ["MemoryStore", "VectorStore"]),
        ("12 tracing",             ["Tracer", "TracedClient"]),
        ("13 hardening",           ["CircuitBreaker", "RateLimiter",
                                    "BudgetGuard", "CachedClient"]),
        ("14 permissions",         ["PermissionPolicy", "GuardedRegistry"]),
        ("14 sandboxing",          ["sandbox_path", "safe_join"]),
        ("14 human in the loop",   ["ApprovalQueue", "approve"]),
    ])
    def test_requirement_is_wired_in(self, root, requirement, needles):
        text = self.src(root)
        assert any(n in text for n in needles), (
            f"requirement {requirement}: none of {needles} appears in "
            f"agent.py or service.py"
        )

    def test_all_stop_conditions_are_configured(self, root):
        text = self.src(root)
        for setting in ("max_steps", "budget_usd"):
            assert setting in text, f"requirement 3: {setting} is not set anywhere"


# ---------------------------------------------------------------- the evals


class TestEvals:
    @pytest.fixture(scope="class")
    def dataset(self, root):
        from agentlib.evals.core import Dataset

        return Dataset.from_jsonl(str(root / "evals" / "dataset.jsonl"))

    def test_at_least_thirty_cases(self, dataset):
        assert len(dataset) >= 30, f"requirement 10: {len(dataset)} cases, need 30"

    def test_at_least_five_negative_cases(self, dataset):
        negative = dataset.filter(tag="negative")
        assert len(negative) >= 5, (
            f"requirement 10: {len(negative)} negative cases, need 5. "
            "Without them, an agent that always acts scores 100%."
        )

    def test_cases_have_unique_ids(self, dataset):
        ids = [c.id for c in dataset]
        assert len(ids) == len(set(ids)), "duplicate case ids"

    def test_no_template_cases_remain(self, dataset):
        leftover = [c.id for c in dataset if "TODO" in str(c.input)
                    or "TODO" in str(c.expected)]
        assert not leftover, f"template cases still in the dataset: {leftover}"

    def test_cases_have_expectations(self, dataset):
        missing = [c.id for c in dataset if c.expected in (None, "", [])]
        assert not missing, f"cases with no expected value: {missing[:5]}"

    def test_checks_module_builds_checks(self, root):
        checks = load(root, "evals/checks".replace("/", os.sep)) if False else None
        path = root / "evals" / "checks.py"
        text = path.read_text()
        assert "def build_checks" in text
        assert "LLMJudge" in text, "requirement 11: an LLM judge is required"
        assert "trajectory" in text, "requirement 11: a trajectory check is required"
        assert "tool_not_called" in text, (
            "requirement 14: guard the irreversible tool on every case"
        )

    def test_the_rubric_is_written(self, root):
        text = (root / "evals" / "checks.py").read_text()
        rubric_start = text.find("RUBRIC")
        assert rubric_start != -1
        rubric = text[rubric_start: rubric_start + 1200]
        assert "TODO" not in rubric, "the rubric is still the template"

    def test_the_runner_has_a_gate(self, root):
        text = (root / "evals" / "run.py").read_text()
        assert "GATE" in text
        assert "GATE = 0.0" not in text, (
            "set the gate to your baseline minus the noise (ch 10, §5)"
        )


# ------------------------------------------------------------- service, mcp


class TestService:
    def test_has_the_endpoints(self, root):
        text = (root / "service.py").read_text()
        for route in ("/runs", "healthz", "stream"):
            assert route in text, f"requirement 15: no {route} endpoint"

    def test_survives_a_restart(self, root):
        text = (root / "service.py").read_text()
        assert "reclaim_stale" in text, (
            "requirement 15: call reclaim_stale() on startup or the service "
            "loses every in-flight run on a deploy"
        )


class TestMCP:
    def test_exposes_or_consumes_mcp(self, root):
        text = source(root, "mcp_server.py", "agent.py")
        assert "MCPServer" in text or "MCPClient" in text or "bridge_tools" in text, (
            "requirement 16: expose a tool over MCP or consume one"
        )

    def test_logs_to_stderr_not_stdout(self, root):
        # one stray print() corrupts the JSON-RPC stream
        text = (root / "mcp_server.py").read_text()
        offenders = [
            line.strip() for line in text.splitlines()
            if line.strip().startswith("print(") and "stderr" not in line
        ]
        assert not offenders, (
            f"stdout is the JSON-RPC stream; log to stderr. Found: {offenders[:3]}"
        )


# ----------------------------------------------------------------- smoke run


class TestSmoke:
    @pytest.mark.skipif(not os.getenv("CAPSTONE_LIVE"),
                        reason="set CAPSTONE_LIVE=1 to run one real agent call")
    def test_one_real_run(self, root):
        agent = load(root, "agent")
        result = agent.run("What can you do?")
        assert isinstance(result, dict)
        for key in ("output", "stop_reason", "cost", "steps",
                    "tool_sequence", "trace_id"):
            assert key in result, f"run() must return {key!r}"
        assert result["output"], "the agent produced no output"
        assert result["trace_id"], (
            "return the trace_id, or an eval failure can never be joined to "
            "the trace that explains it"
        )
