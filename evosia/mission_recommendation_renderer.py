"""Mission Recommendation Integration — artifact renderer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mission_recommendation_models import MissionRecommendations


def render_json(recs: MissionRecommendations, indent: int = 2) -> str:
    return json.dumps(recs.as_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def render_markdown(recs: MissionRecommendations) -> str:
    lines: list[str] = []
    repo = recs.repository
    s = recs.summary

    lines.append(f"# Mission Recommendations — {repo.get('name', 'Unknown')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Governance Approvals | {s.total_governance_approvals} |")
    lines.append(f"| Draft Missions | {s.missions_generated} |")
    lines.append(f"| Total Tasks | {s.total_tasks} |")
    lines.append(f"| Traceability Valid | {'Yes' if s.traceability_validated else 'No'} |")
    lines.append("")

    if s.missions_by_type:
        lines.append("### Missions by Type")
        lines.append("")
        for mtype, count in sorted(s.missions_by_type.items()):
            lines.append(f"- **{mtype}**: {count}")
        lines.append("")

    if recs.draft_missions:
        lines.append("## Draft Missions")
        lines.append("")
        for m in recs.draft_missions:
            lines.append(f"### {m.mission_id}: {m.title}")
            lines.append("")
            lines.append(f"- **State:** {m.state}")
            lines.append(f"- **Type:** {m.mission_type}")
            lines.append(f"- **Effort:** {m.estimated_effort}")
            lines.append(f"- **Priority:** {m.priority_score}")
            lines.append(f"- **Tasks:** {len(m.tasks)}")
            lines.append(f"- **Objective:** {m.objective}")
            lines.append(f"- **Origin:** {m.originating_finding_id}")
            if m.traceability:
                lines.append(f"- **Traceability:** {m.traceability.evidence_summary[:100]}")
            lines.append("")

    return "\n".join(lines)


def save_artifacts(recs: MissionRecommendations, output_dir: Path) -> tuple[Path, Path]:
    from .utils import atomic_write_json
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "MISSION_RECOMMENDATIONS.json"
    md_path = output_dir / "MISSION_RECOMMENDATIONS.md"
    atomic_write_json(json_path, recs.as_dict())
    md_path.write_text(render_markdown(recs), encoding="utf-8")
    return json_path, md_path


def export_missions(recs: MissionRecommendations, missions_dir: Path) -> list[Path]:
    """Export each draft mission as a separate JSON file."""
    from .utils import atomic_write_json
    missions_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for m in recs.draft_missions:
        path = missions_dir / f"{m.mission_id}.json"
        atomic_write_json(path, m.as_dict())
        paths.append(path)
    return paths
