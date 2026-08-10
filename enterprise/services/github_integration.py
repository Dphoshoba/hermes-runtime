"""GitHub Integration — bridges GitHubRepositoryProvider to enterprise backend."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from hermes_v01.github_provider import (
    GitHubRepositoryProvider,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from hermes_v01.providers import RepositoryMetadata

from ..models import Repository


def get_github_provider() -> GitHubRepositoryProvider:
    """Create a GitHub provider instance from environment."""
    token = os.environ.get("GITHUB_TOKEN")
    return GitHubRepositoryProvider(token=token)


def sync_repository_from_github(
    db: Session,
    repo: Repository,
    ref: str | None = None,
) -> Repository:
    """Sync repository metadata from GitHub.

    Fetches latest metadata from GitHub and updates the repository record.
    Returns the updated repository.
    """
    provider = get_github_provider()
    identifier = repo.identifier

    if not identifier:
        raise ValueError(f"Repository {repo.id} has no GitHub identifier set")

    metadata = provider.get_metadata(identifier, ref=ref)
    commit_sha = provider.get_commit_sha(identifier, ref=ref or metadata.default_branch)

    repo.commit_sha = commit_sha
    repo.visibility = metadata.visibility
    repo.language = metadata.language or repo.language
    repo.default_branch = metadata.default_branch
    repo.last_synced_at = datetime.now(timezone.utc)
    repo.metadata_json = {
        **(repo.metadata_json or {}),
        "branches": list(metadata.branches),
        "description": metadata.description,
    }

    db.commit()
    db.refresh(repo)
    return repo


def fetch_github_metadata(identifier: str) -> RepositoryMetadata:
    """Fetch metadata from GitHub for an identifier without a DB record."""
    provider = get_github_provider()
    return provider.get_metadata(identifier)


def parse_github_identifier(url: str) -> str | None:
    """Extract owner/repo from a GitHub URL.

    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - git@github.com:owner/repo.git
      - owner/repo (already correct)
    """
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    if "github.com/" in url:
        parts = url.split("github.com/")[-1]
        if "/" in parts:
            return parts

    if ":" in url and "/" in url:
        parts = url.split(":")[-1]
        if "/" in parts:
            return parts

    if "/" in url and len(url.split("/")) == 2:
        return url

    return None
