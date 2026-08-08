"""Engineering Governance — artifact renderer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .governance_intel_models import EngineeringGovernance


def render_json(gov: EngineeringGovernance, indent: int = 2) -> str:
    return json.dumps(gov.as_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def render_markdown(gov: EngineeringGovernance) -> str:
    lines: list[str] = []
    repo = gov.repository
    s = gov.assessment.summary

    lines.append(f"# Engineering Governance — {repo.get('name', 'Unknown')}")
    lines.append("")
    lines.append("## Approval Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Evaluated | {s.total_evaluated} |")
    lines.append(f"| Approved | {s.approved} |")
    lines.append(f"| Approved with Notes | {s.approved_with_notes} |")
    lines.append(f"| Needs More Evidence | {s.needs_more_evidence} |")
    lines.append(f"| Deferred | {s.deferred} |")
    lines.append(f"| Rejected | {s.rejected} |")
    lines.append(f"| Approval Rate | {s.approval_rate:.0%} |")
    lines.append(f"| Conflicts | {s.conflicts_found} |")
    lines.append(f"| Duplicates | {s.duplicates_found} |")
    lines.append("")

    # Conflicts
    if gov.assessment.conflicts:
        lines.append("## Conflicts")
        lines.append("")
        for c in gov.assessment.conflicts:
            lines.append(f"- **{c.conflict_id}** [{c.severity}]: {c.description}")
            lines.append(f"  - {c.recommendation_a} vs {c.recommendation_b}")
        lines.append("")

    # Duplicates
    if gov.assessment.duplicates:
        lines.append("## Duplicates")
        lines.append("")
        for d in gov.assessment.duplicates:
            lines.append(f"- **{d.duplicate_id}** [{d.similarity}]: {d.duplicate} → {d.primary}")
        lines.append("")

    # Approved missions
    if gov.assessment.approved_missions:
        lines.append("## Approved Candidate Missions")
        lines.append("")
        for m in gov.assessment.approved_missions:
            lines.append(f"- **{m.finding_id}**: {m.recommendation}")
            lines.append(f"  - Type: {m.mission_type} | Effort: {m.effort} | Risk: {m.risk} | Priority: {m.priority_score}")
        lines.append("")

    # Rejected
    rejected = [d for d in gov.assessment.approval_decisions if d.decision == "REJECTED"]
    if rejected:
        lines.append("## Rejected")
        lines.append("")
        for d in rejected:
            lines.append(f"- **{d.finding_id}**: {d.rationale}")
        lines.append("")

    return "\n".join(lines)


def save_artifacts(gov: EngineeringGovernance, output_dir: Path) -> tuple[Path, Path]:
    from .utils import atomic_write_json
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ENGINEERING_GOVERNANCE.json"
    md_path = output_dir / "ENGINEERING_GOVERNANCE.md"
    atomic_write_json(json_path, gov.as_dict())
    md_path.write_text(render_markdown(gov), encoding="utf-8")
    return json_path, md_path
