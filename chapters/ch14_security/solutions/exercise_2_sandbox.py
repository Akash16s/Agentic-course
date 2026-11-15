"""SOLUTION — Chapter 14, Exercise 2."""

from __future__ import annotations

from pathlib import Path

from agentlib import errors


class PathEscape(errors.LLMError):
    retryable = False


def sandbox_path(root: str | Path, candidate: str) -> Path:
    """Resolve `candidate` inside `root`, or raise PathEscape.

    The attacks this stops, all of which a model will produce when asked nicely by
    a poisoned document:

        ../../../../etc/passwd          traversal
        /etc/passwd                     absolute path
        notes/../../../../etc/passwd    traversal after a legitimate prefix
        a symlink in root pointing out  resolved away by .resolve()

    `.resolve()` before comparing is the whole trick: it collapses `..`, expands
    symlinks, and normalises the separators. Comparing strings without resolving is
    how "blocked ../" checks get bypassed with `....//`.
    """
    root_path = Path(root).resolve()
    target = (root_path / candidate).resolve()
    if target != root_path and root_path not in target.parents:
        raise PathEscape(f"path {candidate!r} escapes the sandbox")
    return target


def safe_join(root: str | Path, candidate: str) -> Path | None:
    """`sandbox_path` that returns None instead of raising."""
    try:
        return sandbox_path(root, candidate)
    except PathEscape:
        return None
