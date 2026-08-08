"""hermes-engineering CLI — Engineering Intelligence commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_ri(args: argparse.Namespace) -> dict:
    """Load Repository Intelligence JSON."""
    repo_root = Path(args.repo).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve() if args.input else repo_root / "repo-intelligence" / "REPOSITORY_INTELLIGENCE.json"
    if not input_path.exists():
        print(json.dumps({"error": f"Repository Intelligence not found: {input_path}"}), file=sys.stderr)
        raise SystemExit(1)
    return json.loads(input_path.read_text(encoding="utf-8"))


def cmd_scan(args: argparse.Namespace) -> int:
    """Consume Repository Intelligence and generate Engineering Intelligence."""
    from .engineering_analyzer import analyze_engineering
    from .engineering_renderer import save_artifacts

    ri = _load_ri(args)
    intelligence = analyze_engineering(ri)

    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path, md_path = save_artifacts(intelligence, output_dir)

    print(json.dumps({
        "status": "analyzed",
        "repository": ri.get("repository", {}).get("name", "unknown"),
        "json_path": str(json_path),
        "md_path": str(md_path),
        "findings": intelligence.summary.total_findings,
        "recommendations": intelligence.summary.total_recommendations,
        "missions": intelligence.summary.total_candidate_missions,
        "health_score": intelligence.summary.health_score,
    }, indent=2, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Print canonical JSON from persisted engineering intelligence."""
    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path = output_dir / "ENGINEERING_INTELLIGENCE.json"
    if not json_path.exists():
        print(json.dumps({"error": f"Engineering Intelligence not found: {json_path}"}), file=sys.stderr)
        return 1
    data = json.loads(json_path.read_text(encoding="utf-8"))
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Print executive engineering summary (Markdown)."""
    from .engineering_analyzer import analyze_engineering
    from .engineering_renderer import render_markdown

    ri = _load_ri(args)
    intelligence = analyze_engineering(ri)
    print(render_markdown(intelligence))
    return 0


def cmd_findings(args: argparse.Namespace) -> int:
    """Print findings grouped by category."""
    from .engineering_analyzer import analyze_engineering

    ri = _load_ri(args)
    intelligence = analyze_engineering(ri)

    grouped: dict[str, list] = {}
    for f in intelligence.findings:
        grouped.setdefault(f.category, []).append(f.as_dict())

    output = {
        "total": intelligence.summary.total_findings,
        "categories": {
            cat: {
                "count": len(items),
                "findings": items,
            }
            for cat, items in sorted(grouped.items())
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def cmd_missions(args: argparse.Namespace) -> int:
    """Print candidate missions only."""
    from .engineering_analyzer import analyze_engineering

    ri = _load_ri(args)
    intelligence = analyze_engineering(ri)

    missions = [m.as_dict() for m in intelligence.candidate_missions]
    print(json.dumps({
        "total": len(missions),
        "missions": missions,
    }, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hermes Engineering Intelligence — evidence-based engineering recommendations"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Path to REPOSITORY_INTELLIGENCE.json (default: <repo>/repo-intelligence/REPOSITORY_INTELLIGENCE.json)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for engineering intelligence artifacts (default: <repo>/engineering-intelligence/)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Consume RI and generate Engineering Intelligence")
    subparsers.add_parser("show", help="Print canonical JSON from persisted EI")
    subparsers.add_parser("summary", help="Print executive engineering summary")
    subparsers.add_parser("findings", help="Print findings grouped by category")
    subparsers.add_parser("missions", help="Print candidate missions only")

    args = parser.parse_args()

    # Set defaults for output-dir based on repo
    if args.output_dir is None:
        args.output_dir = str(Path(args.repo).expanduser().resolve() / "engineering-intelligence")

    handlers = {
        "scan": cmd_scan,
        "show": cmd_show,
        "summary": cmd_summary,
        "findings": cmd_findings,
        "missions": cmd_missions,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
