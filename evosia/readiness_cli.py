"""Repository Readiness CLI — hermes-ready.

Assesses whether a repository is suitable for autonomous engineering
before Repository Intelligence begins.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .readiness import assess_readiness


def _format_markdown(result) -> str:
    """Format readiness result as human-readable Markdown."""
    lines = [
        f"# Repository Readiness Assessment",
        "",
        f"**Repository:** `{result.repository}`",
        f"**Branch:** `{result.branch or 'detached'}`",
        f"**Commit:** `{result.commit or 'unknown'}`",
        f"**State:** `{result.readiness_state}`",
        f"**Confidence:** {result.confidence:.0%}",
        f"**Execution Allowed:** {'Yes' if result.execution_allowed else 'No'}",
        "",
    ]

    if result.supported_languages:
        lines.append(f"**Languages:** {', '.join(result.supported_languages)}")
        lines.append("")

    if result.modified_files:
        lines.append(f"## Modified Files ({len(result.modified_files)})")
        for f in result.modified_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if result.untracked_files:
        lines.append(f"## Untracked Files ({len(result.untracked_files)})")
        for f in result.untracked_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if result.deleted_files:
        lines.append(f"## Deleted Files ({len(result.deleted_files)})")
        for f in result.deleted_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if result.staged_files:
        lines.append(f"## Staged Files ({len(result.staged_files)})")
        for f in result.staged_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if result.protected_paths:
        lines.append(f"## Protected Paths ({len(result.protected_paths)})")
        for f in result.protected_paths:
            lines.append(f"- `{f}`")
        lines.append("")

    if result.reasons:
        lines.append("## Reasons")
        for r in result.reasons:
            lines.append(f"- {r}")
        lines.append("")

    if result.recommendations:
        lines.append("## Recommendations")
        for r in result.recommendations:
            lines.append(f"- {r}")
        lines.append("")

    flags = []
    if result.merge_conflicts:
        flags.append("Merge Conflicts")
    if result.detached_head:
        flags.append("Detached HEAD")
    if result.requires_worktree:
        flags.append("Worktree Required")
    if flags:
        lines.append(f"## Flags: {', '.join(flags)}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assess repository readiness for autonomous engineering"
    )
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Path to the repository (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output canonical JSON only",
    )
    parser.add_argument(
        "--protect",
        action="append",
        default=[],
        help="Protect untracked file(s) from EVOSIA consumption (repeatable)",
    )
    args = parser.parse_args()

    result = assess_readiness(
        repo_path=args.repository,
        protected_untracked=args.protect or None,
    )

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(_format_markdown(result))
        print("---")
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))

    return 0 if result.execution_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
