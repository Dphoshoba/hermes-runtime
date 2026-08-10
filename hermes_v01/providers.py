"""Repository Providers — abstraction for repository sources.

Provides a uniform interface for accessing repositories regardless of
whether they are local paths or GitHub-hosted. This abstraction keeps
Repository Intelligence decoupled from specific hosting providers.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepositoryReference:
    """Canonical reference to a repository, regardless of provider."""

    provider: str  # "local" or "github"
    identifier: str  # path or owner/repo
    ref: str | None = None  # branch, tag, or commit SHA
    resolved_path: str | None = None  # local path after materialization

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "provider": self.provider,
            "identifier": self.identifier,
        }
        if self.ref:
            data["ref"] = self.ref
        if self.resolved_path:
            data["resolved_path"] = self.resolved_path
        return data


@dataclass(frozen=True)
class RepositoryMetadata:
    """Metadata observed from a repository."""

    name: str
    default_branch: str
    commit_sha: str | None = None
    visibility: str | None = None  # "public", "private", or None
    language: str | None = None
    description: str | None = None
    branches: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "default_branch": self.default_branch,
        }
        if self.commit_sha:
            data["commit_sha"] = self.commit_sha
        if self.visibility:
            data["visibility"] = self.visibility
        if self.language:
            data["language"] = self.language
        if self.description:
            data["description"] = self.description
        if self.branches:
            data["branches"] = list(self.branches)
        if self.tags:
            data["tags"] = list(self.tags)
        return data


@dataclass(frozen=True)
class PullRequestInfo:
    """Pull request metadata."""

    number: int
    title: str
    state: str  # "open", "closed"
    head_sha: str
    base_branch: str
    author: str | None = None
    url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "number": self.number,
            "title": self.title,
            "state": self.state,
            "head_sha": self.head_sha,
            "base_branch": self.base_branch,
        }
        if self.author:
            data["author"] = self.author
        if self.url:
            data["url"] = self.url
        return data


@dataclass(frozen=True)
class WorkflowRun:
    """GitHub Actions workflow run."""

    id: int
    name: str
    status: str  # "completed", "in_progress", "queued"
    conclusion: str | None = None  # "success", "failure", "cancelled"
    head_sha: str | None = None
    url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
        }
        if self.conclusion:
            data["conclusion"] = self.conclusion
        if self.head_sha:
            data["head_sha"] = self.head_sha
        if self.url:
            data["url"] = self.url
        return data


class RepositoryProvider(ABC):
    """Abstract base class for repository providers."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return provider type identifier."""

    @abstractmethod
    def get_metadata(self, identifier: str, ref: str | None = None) -> RepositoryMetadata:
        """Fetch repository metadata."""

    @abstractmethod
    def list_branches(self, identifier: str) -> list[str]:
        """List branches in the repository."""

    @abstractmethod
    def get_file_content(self, identifier: str, path: str, ref: str | None = None) -> str | None:
        """Retrieve file content at a specific ref."""

    @abstractmethod
    def get_tree(self, identifier: str, path: str = "", ref: str | None = None) -> list[dict[str, str]]:
        """List files/directories at a path."""

    @abstractmethod
    def materialize(self, identifier: str, target: Path, ref: str | None = None) -> Path:
        """Materialize repository to a local directory."""

    def to_reference(self, identifier: str, ref: str | None = None) -> RepositoryReference:
        """Create a RepositoryReference for this provider."""
        return RepositoryReference(
            provider=self.provider_type,
            identifier=identifier,
            ref=ref,
        )


class LocalRepositoryProvider(RepositoryProvider):
    """Provider for local filesystem repositories."""

    @property
    def provider_type(self) -> str:
        return "local"

    def get_metadata(self, identifier: str, ref: str | None = None) -> RepositoryMetadata:
        path = Path(identifier).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Repository not found: {path}")

        # Get branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=path, capture_output=True, text=True,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "main"

        # Get commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path, capture_output=True, text=True,
        )
        commit = result.stdout.strip() if result.returncode == 0 else None

        # Get branches
        result = subprocess.run(
            ["git", "branch", "--list"],
            cwd=path, capture_output=True, text=True,
        )
        branches = tuple(
            b.strip().lstrip("* ")
            for b in result.stdout.splitlines()
            if b.strip()
        )

        name = path.name

        return RepositoryMetadata(
            name=name,
            default_branch=branch,
            commit_sha=commit,
            branches=branches,
        )

    def list_branches(self, identifier: str) -> list[str]:
        path = Path(identifier).resolve()
        result = subprocess.run(
            ["git", "branch", "--list", "--format=%(refname:short)"],
            cwd=path, capture_output=True, text=True,
        )
        return [b.strip() for b in result.stdout.splitlines() if b.strip()]

    def get_file_content(self, identifier: str, path: str, ref: str | None = None) -> str | None:
        repo = Path(identifier).resolve()
        target = repo / path
        if not target.exists():
            return None
        try:
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def get_tree(self, identifier: str, path: str = "", ref: str | None = None) -> list[dict[str, str]]:
        repo = Path(identifier).resolve()
        target = repo / path if path else repo
        if not target.is_dir():
            return []
        entries = []
        for item in sorted(target.iterdir()):
            if item.name.startswith(".") and item.name not in (".gitignore",):
                continue
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "path": str(item.relative_to(repo)),
            })
        return entries

    def materialize(self, identifier: str, target: Path, ref: str | None = None) -> Path:
        source = Path(identifier).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source repository not found: {source}")
        target.mkdir(parents=True, exist_ok=True)
        # Copy using git to preserve history
        subprocess.run(
            ["git", "clone", str(source), str(target)],
            capture_output=True, check=True,
        )
        if ref:
            subprocess.run(
                ["git", "checkout", ref],
                cwd=target, capture_output=True, check=True,
            )
        return target
