"""Tests for Hermes Safety — Worktree Isolation and Diff Scope Validation.

Covers:
- Source repo with untracked files
- Isolated worktree creation
- Untracked-file contamination prevention
- Mission scope verification against baseline commit
- Detection when a supposedly "modified" file is actually newly added
- Diff-vs-scope validation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermes_v01.safety import (
    DiffScopeCheck,
    WorktreeIsolationCheck,
    check_diff_scope,
    check_worktree_isolation,
)


@pytest.fixture
def git_repo(tmp_path: Path):
    """Create a temporary git repository with a commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True,
    )
    # Initial commit
    (repo / "main.txt").write_text("initial content")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True,
    )
    return repo


@pytest.fixture
def git_repo_with_untracked(git_repo: Path):
    """Git repo with an untracked file."""
    (git_repo / "untracked.txt").write_text("user work")
    return git_repo


def _get_commit_hash(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _create_worktree(repo: Path, worktree_path: Path, branch: str, commit: str):
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(worktree_path), commit],
        cwd=repo, capture_output=True,
    )


class TestWorktreeIsolation:
    """Verify worktree contamination detection."""

    def test_clean_worktree_passes(self, git_repo: Path):
        """Worktree with no untracked files should pass."""
        commit = _get_commit_hash(git_repo)
        wt = git_repo.parent / "wt-clean"
        _create_worktree(git_repo, wt, "test-branch", commit)

        check = check_worktree_isolation(git_repo, wt, commit)
        assert check.passed
        assert len(check.contaminated_files) == 0

    def test_untracked_file_detected(self, git_repo_with_untracked: Path):
        """Untracked file in source should be detected."""
        commit = _get_commit_hash(git_repo_with_untracked)
        wt = git_repo_with_untracked.parent / "wt-untracked"
        _create_worktree(git_repo_with_untracked, wt, "test-branch", commit)

        check = check_worktree_isolation(git_repo_with_untracked, wt, commit)
        assert check.passed  # worktree is clean, no contamination yet
        assert "untracked.txt" in check.source_untracked

    def test_contamination_detected(self, git_repo_with_untracked: Path):
        """Copying untracked file to worktree should be detected."""
        commit = _get_commit_hash(git_repo_with_untracked)
        wt = git_repo_with_untracked.parent / "wt-contaminated"
        _create_worktree(git_repo_with_untracked, wt, "test-branch", commit)

        # Simulate the Pilot 005 error: copy untracked file
        (wt / "untracked.txt").write_text("user work")

        check = check_worktree_isolation(git_repo_with_untracked, wt, commit)
        assert not check.passed
        assert "untracked.txt" in check.contaminated_files

    def test_authorized_untracked_passes(self, git_repo_with_untracked: Path):
        """Explicitly authorized untracked file should not be flagged."""
        commit = _get_commit_hash(git_repo_with_untracked)
        wt = git_repo_with_untracked.parent / "wt-authorized"
        _create_worktree(git_repo_with_untracked, wt, "test-branch", commit)

        # Copy untracked file but authorize it
        (wt / "untracked.txt").write_text("user work")

        check = check_worktree_isolation(
            git_repo_with_untracked, wt, commit,
            authorized_untracked=["untracked.txt"],
        )
        assert check.passed

    def test_multiple_untracked_files(self, git_repo: Path):
        """Multiple untracked files should all be detected."""
        (git_repo / "file1.txt").write_text("a")
        (git_repo / "file2.txt").write_text("b")
        commit = _get_commit_hash(git_repo)

        wt = git_repo.parent / "wt-multi"
        _create_worktree(git_repo, wt, "test-branch", commit)

        # Copy both untracked files
        (wt / "file1.txt").write_text("a")
        (wt / "file2.txt").write_text("b")

        check = check_worktree_isolation(git_repo, wt, commit)
        assert not check.passed
        assert len(check.contaminated_files) == 2


class TestDiffScope:
    """Verify diff-vs-scope validation."""

    def test_single_file_edit_passes(self, git_repo: Path):
        """Editing a single file within scope should pass."""
        commit = _get_commit_hash(git_repo)
        wt = git_repo.parent / "wt-scope"
        _create_worktree(git_repo, wt, "test-branch", commit)

        # Make a small edit
        (wt / "main.txt").write_text("modified content")
        subprocess.run(["git", "add", "."], cwd=wt, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "edit"],
            cwd=wt, capture_output=True,
        )
        new_commit = _get_commit_hash(wt)

        check = check_diff_scope(
            wt, new_commit,
            expected_scope="modify main.txt",
            allowed_file_patterns=["main.txt"],
        )
        assert check.passed
        assert check.modified_files == ["main.txt"]
        assert check.added_files == []

    def test_new_file_detected(self, git_repo: Path):
        """Adding a new file should be detected."""
        commit = _get_commit_hash(git_repo)
        wt = git_repo.parent / "wt-newfile"
        _create_worktree(git_repo, wt, "test-branch", commit)

        # Add new file
        (wt / "new.txt").write_text("new content")
        subprocess.run(["git", "add", "."], cwd=wt, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add new"],
            cwd=wt, capture_output=True,
        )
        new_commit = _get_commit_hash(wt)

        check = check_diff_scope(
            wt, new_commit,
            expected_scope="modify main.txt",
            forbid_new_files=True,
        )
        assert not check.passed
        assert "new.txt" in check.added_files
        assert any("New files added" in v for v in check.scope_violations)

    def test_file_outside_scope_detected(self, git_repo: Path):
        """Editing a file outside allowed patterns should be detected."""
        commit = _get_commit_hash(git_repo)
        wt = git_repo.parent / "wt-outside"
        _create_worktree(git_repo, wt, "test-branch", commit)

        # Edit file outside scope
        (wt / "main.txt").write_text("modified")
        (wt / "other.txt").write_text("new")
        subprocess.run(["git", "add", "."], cwd=wt, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "mixed edit"],
            cwd=wt, capture_output=True,
        )
        new_commit = _get_commit_hash(wt)

        check = check_diff_scope(
            wt, new_commit,
            expected_scope="only main.txt",
            allowed_file_patterns=["main.txt"],
        )
        assert not check.passed
        assert any("outside allowed scope" in v for v in check.scope_violations)

    def test_insertion_limit_enforced(self, git_repo: Path):
        """Exceeding max insertions should fail."""
        commit = _get_commit_hash(git_repo)
        wt = git_repo.parent / "wt-limit"
        _create_worktree(git_repo, wt, "test-branch", commit)

        # Large insertion
        (wt / "main.txt").write_text("line\n" * 100)
        subprocess.run(["git", "add", "."], cwd=wt, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "large edit"],
            cwd=wt, capture_output=True,
        )
        new_commit = _get_commit_hash(wt)

        check = check_diff_scope(
            wt, new_commit,
            expected_scope="small edit",
            max_insertions=10,
        )
        assert not check.passed
        assert any("exceed max" in v for v in check.scope_violations)

    def test_scope_violation_message(self, git_repo: Path):
        """Scope violations should be reflected in message."""
        commit = _get_commit_hash(git_repo)
        wt = git_repo.parent / "wt-msg"
        _create_worktree(git_repo, wt, "test-branch", commit)

        (wt / "unexpected.txt").write_text("oops")
        subprocess.run(["git", "add", "."], cwd=wt, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "wrong file"],
            cwd=wt, capture_output=True,
        )
        new_commit = _get_commit_hash(wt)

        check = check_diff_scope(
            wt, new_commit,
            expected_scope="modify main.txt",
            allowed_file_patterns=["main.txt"],
        )
        assert not check.passed
        assert "Scope violations" in check.message
