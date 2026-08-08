"""hermes-governance CLI — Engineering Governance commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_ei(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve() if args.input else repo_root / "engineering-intelligence" / "ENGINEERING_INTELLIGENCE.json"
    if not input_path.exists():
        print(json.dumps({"error": f"Engineering Intelligence not found: {input_path}"}), file=sys.stderr)
        raise SystemExit(1)
    return json.loads(input_path.read_text(encoding="utf-8"))


def cmd_scan(args: argparse.Namespace) -> int:
    from .governance_analyzer import govern_engineering
    from .governance_renderer import save_artifacts
    ei = _load_ei(args)
    gov = govern_engineering(ei)
    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path, md_path = save_artifacts(gov, output_dir)
    s = gov.assessment.summary
    print(json.dumps({
        "status": "governed", "repository": ei.get("repository", {}).get("name", "unknown"),
        "json_path": str(json_path), "md_path": str(md_path),
        "total_evaluated": s.total_evaluated, "approved": s.approved,
        "approved_with_notes": s.approved_with_notes, "needs_more_evidence": s.needs_more_evidence,
        "deferred": s.deferred, "rejected": s.rejected,
        "conflicts": s.conflicts_found, "duplicates": s.duplicates_found,
        "approval_rate": s.approval_rate,
    }, indent=2, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    json_path = output_dir / "ENGINEERING_GOVERNANCE.json"
    if not json_path.exists():
        print(json.dumps({"error": f"Governance not found: {json_path}"}), file=sys.stderr)
        return 1
    print(json.dumps(json.loads(json_path.read_text(encoding="utf-8")), indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    from .governance_analyzer import govern_engineering
    from .governance_renderer import render_markdown
    ei = _load_ei(args)
    gov = govern_engineering(ei)
    print(render_markdown(gov))
    return 0


def cmd_approved(args: argparse.Namespace) -> int:
    from .governance_analyzer import govern_engineering
    ei = _load_ei(args)
    gov = govern_engineering(ei)
    approved = [m.as_dict() for m in gov.assessment.approved_missions]
    print(json.dumps({"total": len(approved), "missions": approved}, indent=2, sort_keys=True))
    return 0


def cmd_rejected(args: argparse.Namespace) -> int:
    from .governance_analyzer import govern_engineering
    ei = _load_ei(args)
    gov = govern_engineering(ei)
    rejected = [d.as_dict() for d in gov.assessment.approval_decisions if d.decision == "REJECTED"]
    print(json.dumps({"total": len(rejected), "decisions": rejected}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes Engineering Governance")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--input", default=None)
    parser.add_argument("--output-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    sub.add_parser("show")
    sub.add_parser("summary")
    sub.add_parser("approved")
    sub.add_parser("rejected")
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = str(Path(args.repo).expanduser().resolve() / "engineering-governance")
    handlers = {"scan": cmd_scan, "show": cmd_show, "summary": cmd_summary,
                "approved": cmd_approved, "rejected": cmd_rejected}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
