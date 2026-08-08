"""hermes-recommend CLI — Mission Recommendation Integration commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .mission_recommendation_models import DraftMission, TraceabilityLink, GeneratedTask, _VALID_STATES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_gov(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve() if args.input else repo_root / "engineering-governance" / "ENGINEERING_GOVERNANCE.json"
    if not input_path.exists():
        print(json.dumps({"error": f"Governance not found: {input_path}"}), file=sys.stderr)
        raise SystemExit(1)
    return json.loads(input_path.read_text(encoding="utf-8"))


def _load_missions(output_dir: Path) -> tuple[list[DraftMission], dict[str, Any]]:
    """Load all missions from generated_missions directory."""
    missions_dir = output_dir / "generated_missions"
    if not missions_dir.exists():
        return [], {}
    recs_path = output_dir / "MISSION_RECOMMENDATIONS.json"
    recs_data = json.loads(recs_path.read_text(encoding="utf-8")) if recs_path.exists() else {}
    missions: list[DraftMission] = []
    for p in sorted(missions_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        missions.append(_parse_mission(data))
    return missions, recs_data


def _parse_mission(data: dict[str, Any]) -> DraftMission:
    meta = data.get("metadata", {})
    trace_data = meta.get("traceability")
    traceability = None
    if trace_data:
        traceability = TraceabilityLink(
            governance_finding_id=trace_data.get("governance_finding_id", ""),
            engineering_finding_id=trace_data.get("engineering_finding_id", ""),
            recommendation_text=trace_data.get("recommendation_text", ""),
            repository_intelligence_source=trace_data.get("repository_intelligence_source", ""),
            evidence_summary=trace_data.get("evidence_summary", ""),
        )
    tasks = tuple(
        GeneratedTask(
            task_id=t["task_id"], title=t["title"], command=t["command"],
            dependencies=tuple(t.get("dependencies", ())),
            priority=t.get("priority", 100),
            required_capabilities=tuple(t.get("required_capabilities", ())),
            working_directory=t.get("working_directory"),
        )
        for t in data.get("tasks", [])
    )
    return DraftMission(
        mission_id=data["mission_id"], title=data["title"],
        description=data.get("description", ""),
        objective=meta.get("objective", ""),
        tasks=tasks,
        goals=tuple(data.get("goals", ())),
        constraints=tuple(data.get("constraints", ())),
        required_capabilities=tuple(data.get("required_capabilities", ())),
        working_directory=data.get("working_directory"),
        repository=data.get("repository"),
        state=meta.get("state", "DRAFT"),
        traceability=traceability,
        originating_finding_id=meta.get("originating_finding_id", ""),
        originating_recommendation=meta.get("originating_recommendation", ""),
        governance_approval_reference=meta.get("governance_approval_reference", ""),
        estimated_effort=meta.get("estimated_effort", ""),
        priority_score=meta.get("priority_score", 0.0),
        mission_type=meta.get("mission_type", ""),
        approved_at=meta.get("approved_at", ""),
        approved_by=meta.get("approved_by", ""),
        rejection_reason=meta.get("rejection_reason", ""),
    )


def _save_mission(mission: DraftMission, output_dir: Path) -> Path:
    path = output_dir / "generated_missions" / f"{mission.mission_id}.json"
    from .utils import atomic_write_json
    atomic_write_json(path, mission.as_dict())
    return path


def _find_mission(missions: list[DraftMission], mission_id: str) -> DraftMission | None:
    for m in missions:
        if m.mission_id == mission_id:
            return m
    return None


def _mission_summary(m: DraftMission) -> dict[str, Any]:
    d: dict[str, Any] = {
        "mission_id": m.mission_id,
        "title": m.title,
        "state": m.state,
        "mission_type": m.mission_type,
        "priority_score": m.priority_score,
        "tasks": len(m.tasks),
        "originating_finding_id": m.originating_finding_id,
    }
    if m.is_approved:
        d["approved_at"] = m.approved_at
        d["approved_by"] = m.approved_by
    if m.is_rejected:
        d["rejection_reason"] = m.rejection_reason
    return d


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

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


def cmd_approve(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    missions, _ = _load_missions(output_dir)
    m = _find_mission(missions, args.mission)
    if m is None:
        print(json.dumps({"error": f"Mission not found: {args.mission}"}), file=sys.stderr)
        return 1
    if not m.is_draft:
        print(json.dumps({"error": f"Mission {m.mission_id} is not in DRAFT state (state={m.state})"}), file=sys.stderr)
        return 1
    approved = m.approve(by=args.by or "human", reason=args.reason or "")
    _save_mission(approved, output_dir)
    print(json.dumps({
        "status": "approved", **_mission_summary(approved),
        "approved_at": approved.approved_at, "approved_by": approved.approved_by,
    }, indent=2, sort_keys=True))
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    missions, _ = _load_missions(output_dir)
    m = _find_mission(missions, args.mission)
    if m is None:
        print(json.dumps({"error": f"Mission not found: {args.mission}"}), file=sys.stderr)
        return 1
    if not m.is_draft:
        print(json.dumps({"error": f"Mission {m.mission_id} is not in DRAFT state (state={m.state})"}), file=sys.stderr)
        return 1
    rejected = m.reject(reason=args.reason or "rejected by operator", by=args.by or "human")
    _save_mission(rejected, output_dir)
    print(json.dumps({
        "status": "rejected", **_mission_summary(rejected),
        "rejection_reason": rejected.rejection_reason,
    }, indent=2, sort_keys=True))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    missions, _ = _load_missions(output_dir)
    if args.mission:
        m = _find_mission(missions, args.mission)
        if m is None:
            print(json.dumps({"error": f"Mission not found: {args.mission}"}), file=sys.stderr)
            return 1
        print(json.dumps(_mission_summary(m), indent=2, sort_keys=True))
    else:
        summaries = [_mission_summary(m) for m in missions]
        print(json.dumps({"missions": summaries, "total": len(summaries)}, indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
    approve_p = sub.add_parser("approve")
    approve_p.add_argument("mission")
    approve_p.add_argument("--by", default=None)
    approve_p.add_argument("--reason", default=None)
    reject_p = sub.add_parser("reject")
    reject_p.add_argument("mission")
    reject_p.add_argument("--by", default=None)
    reject_p.add_argument("--reason", default=None)
    status_p = sub.add_parser("status")
    status_p.add_argument("mission", nargs="?", default=None)
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = str(Path(args.repo).expanduser().resolve() / "mission-recommendations")
    handlers = {
        "generate": cmd_generate, "show": cmd_show, "summary": cmd_summary,
        "export": cmd_export, "approve": cmd_approve, "reject": cmd_reject, "status": cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
