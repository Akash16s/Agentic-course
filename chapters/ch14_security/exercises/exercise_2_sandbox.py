"""EXERCISE 2 — Path sandboxing.

    pytest chapters/ch14_security/tests -q -k sandbox
"""

from __future__ import annotations

from pathlib import Path

from agentlib import errors


class PathEscape(errors.LLMError):
    """A path resolved outside its sandbox. Not retryable."""

    retryable = False


def sandbox_path(root: str | Path, candidate: str) -> Path:
    """Resolve `candidate` inside `root`, or raise PathEscape.

    Spec:
        root_path = Path(root).resolve()
        target    = (root_path / candidate).resolve()
        if target != root_path and root_path not in target.parents:
            raise PathEscape(...)
        return target

    `.resolve()` BEFORE COMPARING IS THE WHOLE TRICK. It collapses `..`, expands
    symlinks and normalises separators, so you compare real locations rather than
    strings. Checking "does the string contain `..`?" is bypassable, and everyone
    who has shipped that check has eventually found out how.

    Note also that `Path(root) / "/etc/passwd"` yields `/etc/passwd` — pathlib lets
    an absolute component win outright. Resolve-then-contain catches that too,
    which a naive prefix check would not.

    `root_path not in target.parents` rather than a `str.startswith` check:
    startswith would accept a sibling directory whose name merely begins with the
    root's ("/data" and "/data-backup").
    """
    # TODO: implement
    raise NotImplementedError


def safe_join(root: str | Path, candidate: str) -> Path | None:
    """`sandbox_path` that returns None instead of raising.

    Useful where you want a tool to report "no such file" rather than surfacing
    that a sandbox exists at all.
    """
    # TODO: implement
    raise NotImplementedError
