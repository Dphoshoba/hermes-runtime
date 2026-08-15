"""GitHub Integration CLI — hermes-github.

Read-only inspection of GitHub repositories through the EVOSIA pipeline.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .github_provider import (
    GitHubRepositoryProvider,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    _parse_repo_ref,
)
from .readiness import assess_readiness


def _format_markdown(metadata, identifier: str) -> str:
    """Format GitHub metadata as human-readable Markdown."""
    lines = [
        f"# GitHub Repository: {identifier}",
        "",
        f"**Name:** {metadata.name}",
        f"**Default Branch:** {metadata.default_branch}",
    ]
    if metadata.commit_sha:
        lines.append(f"**Commit SHA:** {metadata.commit_sha}")
    if metadata.visibility:
        lines.append(f"**Visibility:** {metadata.visibility}")
    if metadata.language:
        lines.append(f"**Language:** {metadata.language}")
    if metadata.description:
        lines.append(f"**Description:** {metadata.description}")
    lines.append("")

    if metadata.branches:
        lines.append(f"## Branches ({len(metadata.branches)})")
        for b in metadata.branches:
            lines.append(f"- {b}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EVOSIA GitHub integration (read-only)"
    )
    parser.add_argument(
        "command",
        choices=["inspect", "branches", "files", "pr", "actions", "ready"],
        help="Command to execute",
    )
    parser.add_argument(
        "repository",
        help="Repository in owner/repo or owner/repo@ref format",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Branch, tag, or commit SHA",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output canonical JSON only",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub token (prefer GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--materialize-to",
        type=Path,
        default=None,
        help="Clone repository to this path for local analysis",
    )
    args = parser.parse_args()

    provider = GitHubRepositoryProvider(token=args.token)
    repo_id, repo_ref = _parse_repo_ref(args.repository)
    ref = args.ref or repo_ref

    try:
        if args.command == "inspect":
            metadata = provider.get_metadata(repo_id, ref)
            if args.json:
                print(json.dumps(metadata.as_dict(), indent=2, sort_keys=True))
            else:
                print(_format_markdown(metadata, args.repository))

        elif args.command == "branches":
            branches = provider.list_branches(repo_id)
            if args.json:
                print(json.dumps(branches, indent=2))
            else:
                print(f"Branches for {repo_id}:")
                for b in branches:
                    print(f"  - {b}")

        elif args.command == "files":
            tree = provider.get_tree(repo_id, ref=ref)
            if args.json:
                print(json.dumps(tree, indent=2))
            else:
                print(f"Files in {repo_id}:")
                for entry in tree:
                    prefix = "  " if entry["type"] == "file" else "[dir] "
                    print(f"  {prefix}{entry['name']}")

        elif args.command == "pr":
            prs = provider.get_pull_requests(repo_id)
            if args.json:
                print(json.dumps([pr.as_dict() for pr in prs], indent=2))
            else:
                print(f"Pull Requests for {repo_id}:")
                for pr in prs:
                    print(f"  #{pr.number}: {pr.title} [{pr.state}]")

        elif args.command == "actions":
            runs = provider.get_workflow_runs(repo_id, branch=ref)
            if args.json:
                print(json.dumps([r.as_dict() for r in runs], indent=2))
            else:
                print(f"Workflow runs for {repo_id}:")
                for run in runs:
                    conclusion = run.conclusion or "pending"
                    print(f"  {run.name}: {run.status} ({conclusion})")

        elif args.command == "ready":
            if not args.materialize_to:
                print("Error: --materialize-to required for 'ready' command")
                return 1
            print(f"Materializing {repo_id} to {args.materialize_to}...")
            provider.materialize(repo_id, args.materialize_to, ref=ref)
            print("Running readiness assessment...")
            readiness = assess_readiness(args.materialize_to)
            if args.json:
                print(json.dumps(readiness.as_dict(), indent=2, sort_keys=True))
            else:
                print(f"Readiness: {readiness.readiness_state}")
                print(f"Execution allowed: {readiness.execution_allowed}")
                print(f"Languages: {', '.join(readiness.supported_languages)}")
                if readiness.reasons:
                    print("Reasons:")
                    for r in readiness.reasons:
                        print(f"  - {r}")
                if readiness.recommendations:
                    print("Recommendations:")
                    for r in readiness.recommendations:
                        print(f"  - {r}")
            return 0 if readiness.execution_allowed else 1

    except GitHubAuthenticationError as e:
        print(f"Authentication error: {e}")
        return 2
    except GitHubNotFoundError as e:
        print(f"Not found: {e}")
        return 3
    except GitHubRateLimitError as e:
        print(f"Rate limit: {e}")
        return 4
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
