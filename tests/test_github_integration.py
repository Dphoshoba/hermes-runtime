"""Tests for GitHub Integration — Provider Abstraction and Read-Only Safety.

Covers:
- Provider abstraction (local provider)
- RepositoryReference determinism
- Local provider backward compatibility
- Read-only enforcement
- Token redaction
- GitHub provider (mocked)
- Materialization
- Readiness integration
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from hermes_v01.providers import (
    LocalRepositoryProvider,
    RepositoryMetadata,
    RepositoryReference,
)
from hermes_v01.github_provider import (
    GitHubRepositoryProvider,
    ReadOnlyViolation,
    _redact_token,
    _parse_repo_ref,
)
from hermes_v01.readiness import assess_readiness


@pytest.fixture
def git_repo(tmp_path: Path):
    """Create a temporary git repository."""
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
    (repo / "main.py").write_text("def hello(): pass\n")
    (repo / "utils.py").write_text("def helper(): pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True,
    )
    return repo


class TestRepositoryReference:
    def test_deterministic(self):
        r1 = RepositoryReference(provider="github", identifier="owner/repo", ref="main")
        r2 = RepositoryReference(provider="github", identifier="owner/repo", ref="main")
        assert r1 == r2

    def test_as_dict(self):
        ref = RepositoryReference(provider="github", identifier="owner/repo", ref="v1.0")
        d = ref.as_dict()
        assert d["provider"] == "github"
        assert d["identifier"] == "owner/repo"
        assert d["ref"] == "v1.0"

    def test_as_dict_no_ref(self):
        ref = RepositoryReference(provider="local", identifier="/path/to/repo")
        d = ref.as_dict()
        assert "ref" not in d


class TestLocalProvider:
    def test_provider_type(self):
        provider = LocalRepositoryProvider()
        assert provider.provider_type == "local"

    def test_get_metadata(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        meta = provider.get_metadata(str(git_repo))
        assert meta.name == "repo"
        assert meta.default_branch == "main"
        assert meta.commit_sha is not None

    def test_list_branches(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        branches = provider.list_branches(str(git_repo))
        assert "main" in branches

    def test_get_file_content(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        content = provider.get_file_content(str(git_repo), "main.py")
        assert content is not None
        assert "hello" in content

    def test_get_file_content_missing(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        content = provider.get_file_content(str(git_repo), "nonexistent.py")
        assert content is None

    def test_get_tree(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        tree = provider.get_tree(str(git_repo))
        names = [e["name"] for e in tree]
        assert "main.py" in names
        assert "utils.py" in names

    def test_materialize(self, git_repo: Path, tmp_path: Path):
        provider = LocalRepositoryProvider()
        target = tmp_path / "cloned"
        result = provider.materialize(str(git_repo), target)
        assert result.exists()
        assert (result / "main.py").exists()

    def test_to_reference(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        ref = provider.to_reference(str(git_repo))
        assert ref.provider == "local"
        assert ref.identifier == str(git_repo)


class TestTokenRedaction:
    def test_none_token(self):
        assert _redact_token(None) == "<not set>"

    def test_short_token(self):
        assert _redact_token("abc") == "***"

    def test_long_token(self):
        result = _redact_token("ghp_1234567890abcdef")
        assert result.startswith("ghp_")
        assert len(result) == len("ghp_1234567890abcdef")
        assert "*" in result

    def test_preserves_length(self):
        token = "ghp_xxxxxxxxxxxxxxxxxxxx"
        redacted = _redact_token(token)
        assert len(redacted) == len(token)


class TestParseRepoRef:
    def test_owner_repo(self):
        repo, ref = _parse_repo_ref("owner/repo")
        assert repo == "owner/repo"
        assert ref is None

    def test_owner_repo_at_ref(self):
        repo, ref = _parse_repo_ref("owner/repo@main")
        assert repo == "owner/repo"
        assert ref == "main"

    def test_owner_repo_at_sha(self):
        repo, ref = _parse_repo_ref("owner/repo@abc123")
        assert repo == "owner/repo"
        assert ref == "abc123"


class TestGitHubProviderReadOnly:
    def test_provider_type(self):
        provider = GitHubRepositoryProvider(token="dummy")
        assert provider.provider_type == "github"

    def test_read_only_violation_class_exists(self):
        assert issubclass(ReadOnlyViolation, Exception)


class TestGitHubProviderMocked:
    def test_get_metadata(self):
        provider = GitHubRepositoryProvider(token="dummy")
        
        repo_response = json.dumps({
            "name": "test-repo",
            "default_branch": "main",
            "visibility": "public",
            "language": "Python",
            "description": "A test repository",
        }).encode("utf-8")
        
        branches_response = json.dumps([
            {"name": "main"},
            {"name": "develop"},
        ]).encode("utf-8")

        def mock_urlopen(req):
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "branches" in req.full_url:
                mock_resp.read.return_value = branches_response
            else:
                mock_resp.read.return_value = repo_response
            return mock_resp

        with patch("hermes_v01.github_provider.urlopen", side_effect=mock_urlopen):
            meta = provider.get_metadata("owner/test-repo")
            assert meta.name == "test-repo"
            assert meta.default_branch == "main"
            assert meta.visibility == "public"

    def test_list_branches(self):
        provider = GitHubRepositoryProvider(token="dummy")
        mock_response = json.dumps([
            {"name": "main"},
            {"name": "develop"},
        ]).encode("utf-8")

        with patch("hermes_v01.github_provider.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            branches = provider.list_branches("owner/repo")
            assert "main" in branches
            assert "develop" in branches

    def test_get_pull_requests(self):
        provider = GitHubRepositoryProvider(token="dummy")
        mock_response = json.dumps([
            {
                "number": 1,
                "title": "Fix bug",
                "state": "open",
                "head": {"sha": "abc123"},
                "base": {"ref": "main"},
                "user": {"login": "testuser"},
                "html_url": "https://github.com/owner/repo/pull/1",
            },
        ]).encode("utf-8")

        with patch("hermes_v01.github_provider.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            prs = provider.get_pull_requests("owner/repo")
            assert len(prs) == 1
            assert prs[0].number == 1
            assert prs[0].title == "Fix bug"

    def test_get_workflow_runs(self):
        provider = GitHubRepositoryProvider(token="dummy")
        mock_response = json.dumps({
            "workflow_runs": [
                {
                    "id": 123,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": "abc123",
                    "html_url": "https://github.com/owner/repo/actions/runs/123",
                },
            ],
        }).encode("utf-8")

        with patch("hermes_v01.github_provider.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            runs = provider.get_workflow_runs("owner/repo")
            assert len(runs) == 1
            assert runs[0].name == "CI"
            assert runs[0].conclusion == "success"


class TestReadinessIntegration:
    def test_local_provider_readiness(self, git_repo: Path):
        provider = LocalRepositoryProvider()
        meta = provider.get_metadata(str(git_repo))
        readiness = assess_readiness(git_repo)
        assert readiness.execution_allowed is True
        assert readiness.branch == "main"

    def test_materialized_readiness(self, git_repo: Path, tmp_path: Path):
        provider = LocalRepositoryProvider()
        target = tmp_path / "materialized"
        provider.materialize(str(git_repo), target)
        readiness = assess_readiness(target)
        assert readiness.execution_allowed is True
