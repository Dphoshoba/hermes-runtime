"""Repository Readiness — pre-pipeline safety gate.

Determines whether a repository is suitable for autonomous engineering
before Repository Intelligence begins. Every mission begins with a
readiness assessment.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .language_detector import detect_languages


class ReadinessState(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RepositoryReadiness:
    """Canonical result of a readiness assessment."""

    repository: str
    branch: str | None
    commit: str | None
    readiness_state: str
    confidence: float
    supported_languages: tuple[str, ...]
    committed_source_present: bool
    modified_files: tuple[str, ...]
    untracked_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    staged_files: tuple[str, ...]
    merge_conflicts: bool
    detached_head: bool
    requires_worktree: bool
    execution_allowed: bool
    protected_paths: tuple[str, ...]
    reasons: tuple[str, ...]
    recommendations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "branch": self.branch,
            "commit": self.commit,
            "readiness_state": self.readiness_state,
            "confidence": self.confidence,
            "supported_languages": list(self.supported_languages),
            "committed_source_present": self.committed_source_present,
            "modified_files": list(self.modified_files),
            "untracked_files": list(self.untracked_files),
            "deleted_files": list(self.deleted_files),
            "staged_files": list(self.staged_files),
            "merge_conflicts": self.merge_conflicts,
            "detached_head": self.detached_head,
            "requires_worktree": self.requires_worktree,
            "execution_allowed": self.execution_allowed,
            "protected_paths": list(self.protected_paths),
            "reasons": list(self.reasons),
            "recommendations": list(self.recommendations),
        }


def _run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
    """Run a git command. Returns (stdout, stderr, returncode)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    _, _, rc = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return rc == 0


def _get_branch(path: Path) -> str | None:
    """Get current branch name, or None if detached."""
    stdout, _, rc = _run_git(["branch", "--show-current"], cwd=path)
    return stdout if rc == 0 and stdout else None


def _get_commit(path: Path) -> str | None:
    """Get current commit hash."""
    stdout, _, rc = _run_git(["rev-parse", "HEAD"], cwd=path)
    return stdout if rc == 0 else None


def _is_detached(path: Path) -> bool:
    """Check if HEAD is detached."""
    _, _, rc = _run_git(["symbolic-ref", "-q", "HEAD"], cwd=path)
    return rc != 0


def _get_modified_files(path: Path) -> list[str]:
    """Get list of modified (tracked) files."""
    stdout, _, _ = _run_git(["diff", "--name-only"], cwd=path)
    return [f for f in stdout.splitlines() if f]


def _get_untracked_files(path: Path) -> list[str]:
    """Get list of untracked files."""
    stdout, _, _ = _run_git(
        ["ls-files", "--others", "--exclude-standard"], cwd=path
    )
    return [f for f in stdout.splitlines() if f]


def _get_deleted_files(path: Path) -> list[str]:
    """Get list of deleted files."""
    stdout, _, _ = _run_git(["diff", "--name-only", "--diff-filter=D"], cwd=path)
    return [f for f in stdout.splitlines() if f]


def _get_staged_files(path: Path) -> list[str]:
    """Get list of staged files."""
    stdout, _, _ = _run_git(["diff", "--cached", "--name-only"], cwd=path)
    return [f for f in stdout.splitlines() if f]


def _has_merge_conflicts(path: Path) -> bool:
    """Check for unmerged files (merge conflicts)."""
    stdout, _, _ = _run_git(["ls-files", "--unmerged"], cwd=path)
    return bool(stdout.strip())


def _has_committed_source(path: Path) -> bool:
    """Check if repository has any committed source files."""
    stdout, _, _ = _run_git(
        ["ls-tree", "-r", "--name-only", "HEAD"], cwd=path
    )
    return bool(stdout.strip())


def _count_committed_files(path: Path) -> int:
    """Count committed files."""
    stdout, _, _ = _run_git(
        ["ls-tree", "-r", "--name-only", "HEAD"], cwd=path
    )
    return len([f for f in stdout.splitlines() if f])


def assess_readiness(
    repo_path: Path,
    protected_untracked: list[str] | None = None,
) -> RepositoryReadiness:
    """Assess whether a repository is ready for autonomous engineering.

    Args:
        repo_path: Path to the repository.
        protected_untracked: List of untracked files that belong to the
            user and must not be consumed by Hermes.

    Returns:
        RepositoryReadiness with assessment results.
    """
    repo = repo_path.resolve()
    protected = tuple(protected_untracked or [])
    reasons: list[str] = []
    recommendations: list[str] = []

    # Version Control checks
    if not _is_git_repo(repo):
        return RepositoryReadiness(
            repository=str(repo),
            branch=None,
            commit=None,
            readiness_state=ReadinessState.BLOCKED,
            confidence=1.0,
            supported_languages=(),
            committed_source_present=False,
            modified_files=(),
            untracked_files=(),
            deleted_files=(),
            staged_files=(),
            merge_conflicts=False,
            detached_head=False,
            requires_worktree=False,
            execution_allowed=False,
            protected_paths=protected,
            reasons=("Not a git repository",),
            recommendations=("Initialize a git repository before using Hermes",),
        )

    branch = _get_branch(repo)
    commit = _get_commit(repo)
    detached = _is_detached(repo)

    if detached:
        reasons.append("HEAD is detached")
        recommendations.append("Check out a branch before running Hermes")

    # Working Tree checks
    modified = _get_modified_files(repo)
    untracked = _get_untracked_files(repo)
    deleted = _get_deleted_files(repo)
    staged = _get_staged_files(repo)
    conflicts = _has_merge_conflicts(repo)

    if conflicts:
        reasons.append("Merge conflicts detected")
        recommendations.append("Resolve merge conflicts before running Hermes")

    if staged:
        reasons.append(f"{len(staged)} staged file(s) present")
        recommendations.append("Commit or unstage changes before running Hermes")

    # Baseline Integrity checks
    has_source = _has_committed_source(repo)
    file_count = _count_committed_files(repo)

    if not has_source:
        reasons.append("No committed source files")
        recommendations.append("Commit source code before running Hermes")

    if has_source and file_count < 2:
        reasons.append(f"Only {file_count} committed file(s) — likely empty project")
        recommendations.append("Commit meaningful source before running Hermes")

    # Analysis Confidence checks
    try:
        lang_result = detect_languages(repo)
        languages = tuple(
            l["language"] for l in lang_result.get("languages", [])
        )
    except Exception:
        languages = ()

    if not languages:
        reasons.append("No supported languages detected")
        recommendations.append("Ensure repository contains Python, JavaScript, or TypeScript source")

    # Mission Safety checks
    has_user_work = bool(modified or untracked or deleted)
    requires_worktree = has_user_work

    if untracked:
        protected_in_untracked = [f for f in untracked if f in protected]
        if protected_in_untracked:
            reasons.append(
                f"{len(protected_in_untracked)} protected untracked file(s): "
                + ", ".join(protected_in_untracked)
            )
            recommendations.append(
                "Use a git worktree to isolate Hermes changes from user work"
            )

    if modified:
        reasons.append(f"{len(modified)} modified file(s) in working tree")
        recommendations.append(
            "Use a git worktree to isolate Hermes changes from user work"
        )

    # Determine execution_allowed
    execution_allowed = (
        has_source
        and not conflicts
        and not detached
        and bool(languages)
        and file_count >= 2
    )

    # Determine readiness_state
    if execution_allowed and not has_user_work:
        state = ReadinessState.READY
        confidence = 0.9
    elif execution_allowed and has_user_work:
        state = ReadinessState.READY
        confidence = 0.7
        recommendations.append("Working tree has user changes — use a worktree for isolation")
    elif not execution_allowed and reasons:
        state = ReadinessState.NOT_READY
        confidence = 0.8
    else:
        state = ReadinessState.BLOCKED
        confidence = 1.0

    return RepositoryReadiness(
        repository=str(repo),
        branch=branch,
        commit=commit,
        readiness_state=state,
        confidence=confidence,
        supported_languages=languages,
        committed_source_present=has_source,
        modified_files=tuple(modified),
        untracked_files=tuple(untracked),
        deleted_files=tuple(deleted),
        staged_files=tuple(staged),
        merge_conflicts=conflicts,
        detached_head=detached,
        requires_worktree=requires_worktree,
        execution_allowed=execution_allowed,
        protected_paths=protected,
        reasons=tuple(reasons),
        recommendations=tuple(recommendations),
    )


class ReadinessBlocked(Exception):
    """Raised when repository readiness blocks pipeline execution."""

    def __init__(self, readiness: RepositoryReadiness):
        self.readiness = readiness
        reasons = "; ".join(readiness.reasons) if readiness.reasons else "unknown"
        super().__init__(f"Pipeline blocked: {reasons}")


def assert_ready(
    repo_path: Path,
    protected_untracked: list[str] | None = None,
) -> RepositoryReadiness:
    """Assess readiness and raise if execution is not allowed.

    Use this as the mandatory first step in every autonomous pipeline.

    Args:
        repo_path: Path to the repository.
        protected_untracked: User files that must not be consumed.

    Returns:
        RepositoryReadiness if execution is allowed.

    Raises:
        ReadinessBlocked: If execution_allowed is False.
    """
    readiness = assess_readiness(repo_path, protected_untracked)
    if not readiness.execution_allowed:
        raise ReadinessBlocked(readiness)
    return readiness
