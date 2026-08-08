"""hermes-recommend CLI — Mission Recommendation Integration commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_gov(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve() if args.input else repo_root / "engineering-governance" / "ENGINEERING_GOVERNANCE.json"
    if not input_path.exists():
        print(json.dumps({"error": f"Governance not found: {input_path}"}), file=sys.stderr)
        raise SystemExit(1)
    return json.loads(input_path.read_text(encoding="utf-8"))


def cmd_generate(args: argparse.Namespace) -> int:
    from .mission_generator import generate_missions
    from .mission_recommendation_renderer import save_artifacts, export_missions
    gov = _load_gov(args)
    recs = generate_missions(gov)
    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path, md_path = save_artifacts(recs, output_dir)
    missions_dir = output_dir / "generated_missions"
    exported = export_missions(recs, missions_dir)
    print(json.dumps({
        "status": "generated", "repository": gov.get("repository", {}).get("name", "unknown"),
        "json_path": str(json_path), "md_path": str(md_path),
        "missions_dir": str(missions_dir),
        "total_missions": recs.summary.missions_generated,
        "total_tasks": recs.summary.total_tasks,
    }, indent=2, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path = output_dir / "MISSION_RECOMMENDATIONS.json"
    if not json_path.exists():
        print(json.dumps({"error": f"Recommendations not found: {json_path}"}), file=sys.stderr)
        return 1
    print(json.dumps(json.loads(json_path.read_text(encoding="utf-8")), indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    from .mission_generator import generate_missions
    from .mission_recommendation_renderer import render_markdown
    gov = _load_gov(args)
    recs = generate_missions(gov)
    print(render_markdown(recs))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from .mission_generator import generate_missions
    from .mission_recommendation_renderer import export_missions
    gov = _load_gov(args)
    recs = generate_missions(gov)
    missions_dir = Path(args.output_dir).expanduser().resolve() / "generated_missions"
    exported = export_missions(recs, missions_dir)
    print(json.dumps({"exported": len(exported), "directory": str(missions_dir),
                       "files": [str(p) for p in exported]}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes Mission Recommendation Integration")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--input", default=None)
    parser.add_argument("--output-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    sub.add_parser("show")
    sub.add_parser("summary")
    sub.add_parser("export")
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = str(Path(args.repo).expanduser().resolve() / "mission-recommendations")
    handlers = {"generate": cmd_generate, "show": cmd_show, "summary": cmd_summary, "export": cmd_export}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
