"""Tests for Repository Readiness Assessment.

Covers:
- clean repository
- modified files
- untracked files
- merge conflicts
- detached HEAD
- empty repository
- unsupported language
- repository without committed source
- mixed-language repository
- worktree recommendation
- deterministic output
- CLI
- pipeline integration (assert_ready / ReadinessBlocked)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hermes_v01.readiness import (
    ReadinessBlocked,
    ReadinessState,
    RepositoryReadiness,
    assess_readiness,
    assert_ready,
)


@pytest.fixture
def git_repo(tmp_path: Path):
    """Create a temporary git repository with Python source."""
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
    # Create source files
    (repo / "main.py").write_text("def hello(): pass\n")
    (repo / "utils.py").write_text("def helper(): pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True,
    )
    return repo


@pytest.fixture
def js_repo(tmp_path: Path):
    """Create a temporary git repository with JavaScript source."""
    repo = tmp_path / "js-repo"
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
    (repo / "package.json").write_text('{"name": "test"}')
    (repo / "index.js").write_text("console.log('hello');\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True,
    )
    return repo


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True,
    )
    return result.stdout.strip()


class TestCleanRepository:
    def test_ready_state(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert result.readiness_state == ReadinessState.READY
        assert result.execution_allowed is True
        assert result.confidence >= 0.8

    def test_no_reasons(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert len(result.reasons) == 0

    def test_has_branch(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert result.branch == "main"

    def test_has_commit(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert result.commit is not None
        assert len(result.commit) == 40

    def test_committed_source_present(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert result.committed_source_present is True

    def test_no_user_work(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert len(result.modified_files) == 0
        assert len(result.untracked_files) == 0

    def test_python_detected(self, git_repo: Path):
        result = assess_readiness(git_repo)
        assert "python" in result.supported_languages


class TestModifiedFiles:
    def test_modified_triggers_worktree(self, git_repo: Path):
        (git_repo / "main.py").write_text("def modified(): pass\n")
        result = assess_readiness(git_repo)
        assert "main.py" in result.modified_files
        assert result.requires_worktree is True
        assert result.execution_allowed is True

    def test_modified_reduces_confidence(self, git_repo: Path):
        (git_repo / "main.py").write_text("def modified(): pass\n")
        result = assess_readiness(git_repo)
        assert result.confidence < 0.9


class TestUntrackedFiles:
    def test_untracked_detected(self, git_repo: Path):
        (git_repo / "new_file.py").write_text("# new\n")
        result = assess_readiness(git_repo)
        assert "new_file.py" in result.untracked_files

    def test_protected_untracked(self, git_repo: Path):
        (git_repo / "user_work.py").write_text("# user\n")
        result = assess_readiness(
            git_repo, protected_untracked=["user_work.py"]
        )
        assert "user_work.py" in result.protected_paths
        assert any("protected" in r.lower() for r in result.reasons)


class TestMergeConflicts:
    def test_merge_conflict_blocks(self, git_repo: Path):
        # Create a merge conflict scenario
        branch_commit = _run_git(["rev-parse", "HEAD"], git_repo)
        subprocess.run(
            ["git", "checkout", "-b", "branch-a"],
            cwd=git_repo, capture_output=True,
        )
        (git_repo / "main.py").write_text("version A\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "branch a"],
            cwd=git_repo, capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=git_repo, capture_output=True,
        )
        (git_repo / "main.py").write_text("version B\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main edit"],
            cwd=git_repo, capture_output=True,
        )
        result = subprocess.run(
            ["git", "merge", "branch-a"],
            cwd=git_repo, capture_output=True,
        )
        # If merge succeeds without conflict, skip
        if result.returncode == 0:
            pytest.skip("Merge completed without conflict")
        result = assess_readiness(git_repo)
        assert result.merge_conflicts is True
        assert result.execution_allowed is False


class TestDetachedHead:
    def test_detached_head(self, git_repo: Path):
        commit = _run_git(["rev-parse", "HEAD"], git_repo)
        subprocess.run(
            ["git", "checkout", commit],
            cwd=git_repo, capture_output=True,
        )
        result = assess_readiness(git_repo)
        assert result.detached_head is True
        assert result.execution_allowed is False
        assert any("detached" in r.lower() for r in result.reasons)


class TestEmptyRepository:
    def test_empty_repo(self, tmp_path: Path):
        repo = tmp_path / "empty"
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
        result = assess_readiness(repo)
        assert result.committed_source_present is False
        assert result.execution_allowed is False


class TestNoGitRepo:
    def test_not_a_git_repo(self, tmp_path: Path):
        result = assess_readiness(tmp_path)
        assert result.readiness_state == ReadinessState.BLOCKED
        assert result.execution_allowed is False
        assert any("not a git" in r.lower() for r in result.reasons)


class TestWorktreeRecommendation:
    def test_worktree_recommended_with_user_work(self, git_repo: Path):
        (git_repo / "untracked.txt").write_text("user\n")
        result = assess_readiness(git_repo)
        assert result.requires_worktree is True
        assert any("worktree" in r.lower() for r in result.recommendations)


class TestMixedLanguage:
    def test_mixed_python_js(self, git_repo: Path):
        (git_repo / "app.js").write_text("console.log('hi');\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add js"],
            cwd=git_repo, capture_output=True,
        )
        result = assess_readiness(git_repo)
        assert "python" in result.supported_languages
        assert "javascript" in result.supported_languages


class TestDeterministicOutput:
    def test_same_input_same_output(self, git_repo: Path):
        r1 = assess_readiness(git_repo)
        r2 = assess_readiness(git_repo)
        assert r1.as_dict() == r2.as_dict()

    def test_as_dict_roundtrip(self, git_repo: Path):
        result = assess_readiness(git_repo)
        d = result.as_dict()
        assert isinstance(d, dict)
        assert d["repository"] == str(git_repo)
        assert d["execution_allowed"] is True


class TestPipelineIntegration:
    def test_assert_ready_passes(self, git_repo: Path):
        result = assert_ready(git_repo)
        assert result.execution_allowed is True

    def test_assert_ready_raises(self, tmp_path: Path):
        repo = tmp_path / "empty"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        with pytest.raises(ReadinessBlocked):
            assert_ready(repo)

    def test_readiness_blocked_has_readiness(self, tmp_path: Path):
        repo = tmp_path / "empty"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        try:
            assert_ready(repo)
            assert False, "Should have raised"
        except ReadinessBlocked as e:
            assert e.readiness.execution_allowed is False


class TestSingleFileRepo:
    def test_single_file_not_ready(self, tmp_path: Path):
        repo = tmp_path / "single"
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
        (repo / "only.py").write_text("# one file\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "single"],
            cwd=repo, capture_output=True,
        )
        result = assess_readiness(repo)
        assert result.execution_allowed is False
        assert any("1 committed" in r for r in result.reasons)
