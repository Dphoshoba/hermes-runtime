"""Hermes Safety — Worktree Isolation and Mission Scope Validation.

Prevents baseline contamination and validates that commit diffs match
declared mission scope.

Safety Rules:
1. A worktree created from a committed baseline must never consume files
   that are untracked in the source working tree unless the user
   explicitly authorizes those files as mission inputs.
2. The execution/reporting layer must compare the actual Git diff against
   the declared mission scope before declaring success.
3. If a mission claims a small edit but Git reports a whole-file
   addition/rewrite, validation must fail automatically.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorktreeIsolationCheck:
    """Result of worktree isolation validation."""

    source_untracked: list[str]
    worktree_untracked: list[str]
    contaminated_files: list[str]
    passed: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_untracked": self.source_untracked,
            "worktree_untracked": self.worktree_untracked,
            "contaminated_files": self.contaminated_files,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(frozen=True)
class DiffScopeCheck:
    """Result of diff-vs-scope validation."""

    declared_scope: str
    actual_files_changed: list[str]
    added_files: list[str]
    modified_files: list[str]
    deleted_files: list[str]
    total_insertions: int
    total_deletions: int
    scope_violations: list[str]
    passed: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "declared_scope": self.declared_scope,
            "actual_files_changed": self.actual_files_changed,
            "added_files": self.added_files,
            "modified_files": self.modified_files,
            "deleted_files": self.deleted_files,
            "total_insertions": self.total_insertions,
            "total_deletions": self.total_deletions,
            "scope_violations": self.scope_violations,
            "passed": self.passed,
            "message": self.message,
        }


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def check_worktree_isolation(
    source_repo: Path,
    worktree: Path,
    baseline_commit: str,
    authorized_untracked: list[str] | None = None,
) -> WorktreeIsolationCheck:
    """Verify that a worktree was not contaminated by untracked source files.

    Args:
        source_repo: Path to the original repository.
        worktree: Path to the git worktree.
        baseline_commit: The commit hash the worktree was created from.
        authorized_untracked: List of untracked filenames explicitly authorized
            to be copied into the worktree. Empty list means none authorized.

    Returns:
        WorktreeIsolationCheck with contamination details.
    """
    authorized = set(authorized_untracked or [])

    # Get untracked files in source repo
    source_untracked_raw = _run_git(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=source_repo,
    )
    source_untracked = [
        f for f in source_untracked_raw.splitlines() if f
    ]

    # Get untracked files in worktree
    worktree_untracked_raw = _run_git(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=worktree,
    )
    worktree_untracked = [
        f for f in worktree_untracked_raw.splitlines() if f
    ]

    # Files in worktree that were untracked in source but not authorized
    contaminated = [
        f for f in worktree_untracked
        if f in source_untracked and f not in authorized
    ]

    passed = len(contaminated) == 0
    if passed:
        message = "Worktree isolation verified — no unauthorized file contamination"
    else:
        message = (
            f"Worktree contaminated by {len(contaminated)} unauthorized file(s): "
            + ", ".join(contaminated)
        )

    return WorktreeIsolationCheck(
        source_untracked=source_untracked,
        worktree_untracked=worktree_untracked,
        contaminated_files=contaminated,
        passed=passed,
        message=message,
    )


def check_diff_scope(
    worktree: Path,
    commit_hash: str,
    expected_scope: str,
    allowed_file_patterns: list[str] | None = None,
    max_insertions: int | None = None,
    forbid_new_files: bool = False,
) -> DiffScopeCheck:
    """Validate that a commit's diff matches the declared mission scope.

    Args:
        worktree: Path to the git worktree.
        commit_hash: The commit to validate.
        expected_scope: Human-readable description of expected changes.
        allowed_file_patterns: If set, only files matching these patterns
            are allowed to change. None means any file is allowed.
        max_insertions: If set, reject commits with more insertions.
        forbid_new_files: If True, reject commits that add new files.

    Returns:
        DiffScopeCheck with validation details.
    """
    # Get name-status to correctly identify added/modified/deleted
    name_status = _run_git(
        ["diff", "--name-status", f"{commit_hash}~1", commit_hash],
        cwd=worktree,
    )

    # Get numstat for insertion/deletion counts
    numstat = _run_git(
        ["diff", "--numstat", f"{commit_hash}~1", commit_hash],
        cwd=worktree,
    )

    added_files: list[str] = []
    modified_files: list[str] = []
    deleted_files: list[str] = []
    total_insertions = 0
    total_deletions = 0

    for line in name_status.splitlines():
        parts = line.split("\t", maxsplit=1)
        if len(parts) < 2:
            continue
        status, filepath = parts
        if status == "A":
            added_files.append(filepath)
        elif status == "D":
            deleted_files.append(filepath)
        elif status == "M":
            modified_files.append(filepath)
        elif status.startswith("R"):
            # Rename: R100\told\tnew
            modified_files.append(filepath)

    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, deletions, _ = parts
        if ins != "-":
            total_insertions += int(ins) if ins.isdigit() else 0
        if deletions != "-":
            total_deletions += int(deletions) if deletions.isdigit() else 0

    actual_files = added_files + modified_files + deleted_files

    # Check scope violations
    violations: list[str] = []

    if forbid_new_files and added_files:
        violations.append(
            f"New files added: {', '.join(added_files)}"
        )

    if allowed_file_patterns is not None:
        import fnmatch
        for f in actual_files:
            if not any(fnmatch.fnmatch(f, p) for p in allowed_file_patterns):
                violations.append(f"File outside allowed scope: {f}")

    if max_insertions is not None and total_insertions > max_insertions:
        violations.append(
            f"Insertions ({total_insertions}) exceed max ({max_insertions})"
        )

    # Detect whole-file additions that claim to be modifications
    if expected_scope and "modify" in expected_scope.lower():
        for f in added_files:
            violations.append(
                f"File {f} was added (new) but scope claims modification"
            )

    passed = len(violations) == 0
    if passed:
        message = (
            f"Diff scope verified — {len(actual_files)} file(s) changed, "
            f"+{total_insertions}/-{total_deletions} lines"
        )
    else:
        message = f"Scope violations: {'; '.join(violations)}"

    return DiffScopeCheck(
        declared_scope=expected_scope,
        actual_files_changed=actual_files,
        added_files=added_files,
        modified_files=modified_files,
        deleted_files=deleted_files,
        total_insertions=total_insertions,
        total_deletions=total_deletions,
        scope_violations=violations,
        passed=passed,
        message=message,
    )
