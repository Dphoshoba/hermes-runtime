"""GitHub Repository Provider — read-only access to GitHub repositories.

Version 1.0 is strictly read-only. Write operations (push, merge, delete)
are explicitly prohibited and will raise ReadOnlyViolation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .providers import (
    RepositoryMetadata,
    RepositoryProvider,
    PullRequestInfo,
    WorkflowRun,
)


class ReadOnlyViolation(Exception):
    """Raised when a write operation is attempted on a read-only provider."""


class GitHubAuthenticationError(Exception):
    """Raised when GitHub authentication fails."""


class GitHubNotFoundError(Exception):
    """Raised when a GitHub resource is not found."""


class GitHubRateLimitError(Exception):
    """Raised when GitHub API rate limit is exceeded."""


def _redact_token(token: str | None) -> str:
    """Redact a token for safe logging."""
    if not token:
        return "<not set>"
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


def _parse_repo_ref(repo_ref: str) -> tuple[str, str]:
    """Parse 'owner/repo' or 'owner/repo@ref' format.

    Returns (owner/repo, ref_or_none).
    """
    if "@" in repo_ref:
        repo, ref = repo_ref.split("@", 1)
        return repo, ref
    return repo_ref, None


class GitHubRepositoryProvider(RepositoryProvider):
    """Read-only provider for GitHub repositories.

    Uses GitHub REST API v3 for metadata and git for materialization.
    All operations are strictly read-only.
    """

    API_BASE = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "hermes-runtime/1.0",
        }
        if self._token:
            self._headers["Authorization"] = f"token {self._token}"

    @property
    def provider_type(self) -> str:
        return "github"

    def _api_get(self, endpoint: str) -> Any:
        """Make an authenticated GET request to GitHub API."""
        url = f"{self.API_BASE}{endpoint}"
        req = Request(url, headers=self._headers, method="GET")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 401:
                raise GitHubAuthenticationError(
                    f"Authentication failed. Token: {_redact_token(self._token)}"
                )
            if e.code == 404:
                raise GitHubNotFoundError(f"Not found: {endpoint}")
            if e.code == 403:
                raise GitHubRateLimitError(f"Rate limit or forbidden: {endpoint}")
            raise

    def get_metadata(self, identifier: str, ref: str | None = None) -> RepositoryMetadata:
        """Fetch repository metadata from GitHub."""
        data = self._api_get(f"/repos/{identifier}")

        branches = self.list_branches(identifier)

        return RepositoryMetadata(
            name=data.get("name", identifier.split("/")[-1]),
            default_branch=data.get("default_branch", "main"),
            commit_sha=data.get("default_branch") and None,  # filled by ref
            visibility=data.get("visibility"),
            language=data.get("language"),
            description=data.get("description"),
            branches=tuple(branches),
        )

    def list_branches(self, identifier: str) -> list[str]:
        """List branches in a GitHub repository."""
        branches = []
        page = 1
        while True:
            data = self._api_get(f"/repos/{identifier}/branches?per_page=100&page={page}")
            if not data:
                break
            for b in data:
                name = b.get("name", "")
                if name:
                    branches.append(name)
            if len(data) < 100:
                break
            page += 1
        return branches

    def get_file_content(self, identifier: str, path: str, ref: str | None = None) -> str | None:
        """Retrieve file content from GitHub."""
        params = f"?ref={ref}" if ref else ""
        try:
            data = self._api_get(f"/repos/{identifier}/contents/{path}{params}")
            if isinstance(data, dict) and data.get("encoding") == "base64":
                import base64
                return base64.b64decode(data["content"]).decode("utf-8")
            return None
        except GitHubNotFoundError:
            return None

    def get_tree(self, identifier: str, path: str = "", ref: str | None = None) -> list[dict[str, str]]:
        """List files/directories at a path in a GitHub repository."""
        ref = ref or "HEAD"
        endpoint = f"/repos/{identifier}/contents/{path}" if path else f"/repos/{identifier}/contents"
        params = f"?ref={ref}"
        try:
            data = self._api_get(f"{endpoint}{params}")
            if not isinstance(data, list):
                return []
            entries = []
            for item in data:
                entries.append({
                    "name": item.get("name", ""),
                    "type": item.get("type", "file"),
                    "path": item.get("path", ""),
                })
            return sorted(entries, key=lambda e: e["name"])
        except GitHubNotFoundError:
            return []

    def get_pull_requests(self, identifier: str, state: str = "open") -> list[PullRequestInfo]:
        """List pull requests for a repository."""
        data = self._api_get(f"/repos/{identifier}/pulls?state={state}&per_page=30")
        if not isinstance(data, list):
            return []
        prs = []
        for pr in data:
            prs.append(PullRequestInfo(
                number=pr.get("number", 0),
                title=pr.get("title", ""),
                state=pr.get("state", ""),
                head_sha=pr.get("head", {}).get("sha", ""),
                base_branch=pr.get("base", {}).get("ref", ""),
                author=pr.get("user", {}).get("login"),
                url=pr.get("html_url"),
            ))
        return prs

    def get_workflow_runs(self, identifier: str, branch: str | None = None) -> list[WorkflowRun]:
        """List recent GitHub Actions workflow runs."""
        endpoint = f"/repos/{identifier}/actions/runs?per_page=10"
        if branch:
            endpoint += f"&branch={branch}"
        data = self._api_get(endpoint)
        runs = data.get("workflow_runs", [])
        return [
            WorkflowRun(
                id=run.get("id", 0),
                name=run.get("name", ""),
                status=run.get("status", ""),
                conclusion=run.get("conclusion"),
                head_sha=run.get("head_sha"),
                url=run.get("html_url"),
            )
            for run in runs
        ]

    def get_workflow_failure_logs(self, identifier: str, run_id: int) -> str | None:
        """Retrieve failure logs for a workflow run (best-effort).

        Returns plain text logs if accessible, None otherwise.
        """
        try:
            data = self._api_get(f"/repos/{identifier}/actions/runs/{run_id}/jobs")
            jobs = data.get("jobs", [])
            failure_logs = []
            for job in jobs:
                if job.get("conclusion") == "failure":
                    name = job.get("name", "unknown")
                    failure_logs.append(f"Job: {name}")
                    for step in job.get("steps", []):
                        if step.get("conclusion") == "failure":
                            failure_logs.append(f"  Failed step: {step.get('name', '?')}")
            return "\n".join(failure_logs) if failure_logs else None
        except Exception:
            return None

    def get_commit_sha(self, identifier: str, ref: str = "HEAD") -> str | None:
        """Get commit SHA for a ref."""
        try:
            data = self._api_get(f"/repos/{identifier}/git/ref/heads/{ref}")
            return data.get("object", {}).get("sha")
        except (GitHubNotFoundError, Exception):
            return None

    def materialize(
        self,
        identifier: str,
        target: Path,
        ref: str | None = None,
        depth: int = 1,
    ) -> Path:
        """Materialize a GitHub repository to a local directory via git clone.

        This is the ONLY write operation — it writes to the local filesystem
        only. No GitHub API write operations are performed.

        Args:
            identifier: owner/repo format
            target: local directory to clone into
            ref: branch, tag, or commit to checkout
            depth: clone depth (1 for shallow)

        Returns:
            Path to the materialized repository.

        Raises:
            ReadOnlyViolation: Always (this provider never writes to GitHub).
        """
        url = f"https://github.com/{identifier}.git"
        cmd = ["git", "clone"]
        if depth:
            cmd.extend(["--depth", str(depth)])
        if ref:
            cmd.extend(["--branch", ref])
        cmd.extend([url, str(target)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Clone failed: {result.stderr}")

        # Record exact commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=target, capture_output=True, text=True,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            # Write commit reference
            ref_file = target / ".hermes-commit"
            ref_file.write_text(commit, encoding="utf-8")

        return target

    def to_reference(self, identifier: str, ref: str | None = None) -> "RepositoryReference":
        from .providers import RepositoryReference
        return RepositoryReference(
            provider="github",
            identifier=identifier,
            ref=ref,
        )
