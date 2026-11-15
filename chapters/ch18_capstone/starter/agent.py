"""Capstone agent. Fill this in.

Every import below is something you built. If you find yourself writing code that
already exists in agentlib, stop and go and get it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agentlib.agent import Agent, StopReason            # ch 3
from agentlib.context import ContextBudget, truncate_tool_results  # ch 4
from agentlib.cost import CostTracker                   # ch 1
from agentlib.embeddings import CachedEmbedder, HashingEmbedder    # ch 6
from agentlib.hardening import (                        # ch 13
    BudgetGuard,
    CachedClient,
    CircuitBreaker,
    RateLimiter,
)
from agentlib.llm import LLMClient                      # ch 1
from agentlib.memory.long_term import MemoryStore       # ch 6
from agentlib.memory.short_term import SQLiteSessionStore, SummaryBuffer  # ch 5
from agentlib.security import (                         # ch 14
    ApprovalQueue,
    Decision,
    GuardedRegistry,
    PermissionPolicy,
    sandbox_path,
)
from agentlib.tools import ToolRegistry, tool           # ch 2
from agentlib.tracing import TracedClient, TracedRegistry, Tracer  # ch 12

# --------------------------------------------------------------------- config

ROOT = Path(os.getenv("CAPSTONE_ROOT", ".")).resolve()

SYSTEM_PROMPT = """\
TODO: write this last, not first.

Write it after your evals exist, so you can measure whether each sentence earns
its place. Most system prompts are twice as long as they need to be because
nobody ever deleted a line and re-ran the suite.
"""


# ---------------------------------------------------------------------- tools
# REQUIREMENT 2: at least four tools, schemas derived from signatures.
# REQUIREMENT 4: bounded output on every one of them.
# At least one must be irreversible, so requirement 14's HITL has something to do.


@tool
def list_files(directory: str = ".") -> list[str]:
    """TODO. Sandbox the path (ch 14). Cap the number returned (ch 4)."""
    raise NotImplementedError


@tool
def read_file(path: str, max_chars: int = 4000) -> str:
    """TODO. Sandbox the path. Use middle_out for the cap, not a plain slice."""
    raise NotImplementedError


# TODO: two more tools, one of them irreversible.


# ------------------------------------------------------------------ the agent


def build_permission_policy() -> PermissionPolicy:
    """REQUIREMENT 14. Default deny; specific rules BEFORE broad ones."""
    raise NotImplementedError


def build_client(tracer: Tracer) -> Any:
    """REQUIREMENT 1 + 13. Stack the layers and justify the ORDER in DECISIONS.md.

    Suggested, but argue with it:
        RateLimiter -> CircuitBreaker -> CachedClient -> TracedClient -> LLMClient
    Questions your order should answer: does a cache hit consume a rate-limit
    permit? Should a cache hit be blocked by an open breaker?
    """
    raise NotImplementedError


def build_agent(*, session_id: str = "default",
                tracer: Tracer | None = None) -> Agent:
    """Wire everything together. REQUIREMENTS 1-6, 12-14."""
    raise NotImplementedError


def run(task: str, *, session_id: str = "default") -> dict[str, Any]:
    """One run, end to end.

    MUST return a dict with at least:
        output, stop_reason, cost, steps, tool_sequence, trace_id

    Returning the trace_id is what lets an eval failure be joined to the trace
    that explains it. Without it the two systems never meet and you debug twice.
    """
    raise NotImplementedError
