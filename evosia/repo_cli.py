"""hermes-repo CLI — Repository Intelligence commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan a repository and generate intelligence artifacts."""
    from .repo_scanner import scan_repository
    from .repo_analyzer import analyze_repository
    from .repo_renderer import save_artifacts, render_json

    repo_root = Path(args.repo).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not repo_root.is_dir():
        print(json.dumps({"error": f"repository not found: {repo_root}"}), file=sys.stderr)
        return 1

    scan = scan_repository(repo_root)
    intelligence = analyze_repository(scan)
    json_path, md_path = save_artifacts(intelligence, output_dir)

    print(json.dumps({
        "status": "scanned",
        "repository": str(repo_root),
        "json_path": str(json_path),
        "md_path": str(md_path),
    }, indent=2, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Print canonical JSON from persisted intelligence."""
    json_path = Path(args.output_dir).expanduser().resolve() / "REPOSITORY_INTELLIGENCE.json"
    if not json_path.exists():
        print(json.dumps({"error": f"intelligence not found: {json_path}"}), file=sys.stderr)
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Rescan and determine whether persisted intelligence is current."""
    from .repo_scanner import scan_repository
    from .repo_analyzer import analyze_repository
    from .repo_renderer import render_json

    repo_root = Path(args.repo).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path = output_dir / "REPOSITORY_INTELLIGENCE.json"

    if not json_path.exists():
        print(json.dumps({"current": False, "reason": "no persisted intelligence found"}))
        return 1

    # Rescan
    scan = scan_repository(repo_root)
    intelligence = analyze_repository(scan)
    fresh_json = render_json(intelligence)

    # Compare
    existing = json_path.read_text(encoding="utf-8")
    is_current = existing == fresh_json

    result = {
        "current": is_current,
        "persisted_path": str(json_path),
    }
    if not is_current:
        result["reason"] = "repository has changed since last scan"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if is_current else 1


def cmd_summary(args: argparse.Namespace) -> int:
    """Print concise human-readable architectural summary."""
    from .repo_scanner import scan_repository
    from .repo_analyzer import analyze_repository
    from .repo_renderer import render_markdown

    repo_root = Path(args.repo).expanduser().resolve()
    scan = scan_repository(repo_root)
    intelligence = analyze_repository(scan)
    md = render_markdown(intelligence)
    print(md)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EVOSIA Repository Intelligence — static repository analysis"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        default="./repo-intelligence",
        help="Output directory for intelligence artifacts (default: ./repo-intelligence)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan repository and generate intelligence artifacts")
    subparsers.add_parser("show", help="Print canonical JSON from persisted intelligence")
    subparsers.add_parser("check", help="Rescan and check if persisted intelligence is current")
    subparsers.add_parser("summary", help="Print concise architectural summary")

    args = parser.parse_args()

    handlers = {
        "scan": cmd_scan,
        "show": cmd_show,
        "check": cmd_check,
        "summary": cmd_summary,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
