"""Engineering Intelligence — artifact renderer.

Renders EngineeringIntelligence to JSON and Markdown.
The JSON artifact is authoritative; Markdown is derived from the same model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engineering_intel_models import EngineeringIntelligence


def render_json(intelligence: EngineeringIntelligence, indent: int = 2) -> str:
    """Render deterministic JSON from intelligence model."""
    return json.dumps(
        intelligence.as_dict(),
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
    )


def render_markdown(intelligence: EngineeringIntelligence) -> str:
    """Render human-readable Markdown from intelligence model."""
    lines: list[str] = []
    repo = intelligence.repository
    summary = intelligence.summary
    risk = intelligence.risk_assessment

    repo_name = repo.get("name", "Unknown")

    # Header
    lines.append(f"# Engineering Intelligence — {repo_name}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Health Score | {summary.health_score}/100 |")
    lines.append(f"| Overall Risk | {summary.overall_risk} |")
    lines.append(f"| Total Findings | {summary.total_findings} |")
    lines.append(f"| Critical | {summary.critical_count} |")
    lines.append(f"| High | {summary.high_count} |")
    lines.append(f"| Medium | {summary.medium_count} |")
    lines.append(f"| Low | {summary.low_count} |")
    lines.append(f"| Info | {summary.info_count} |")
    lines.append(f"| Recommendations | {summary.total_recommendations} |")
    lines.append(f"| Candidate Missions | {summary.total_candidate_missions} |")
    lines.append("")

    # Risk Assessment
    lines.append("## Risk Assessment")
    lines.append("")
    lines.append(f"**Level:** {risk.level}")
    lines.append("")
    lines.append(f"**Reasoning:** {risk.reasoning}")
    lines.append("")
    if risk.evidence:
        lines.append(f"**Evidence:** {', '.join(risk.evidence)}")
        lines.append("")
    lines.append(f"**Mitigation:** {risk.mitigation}")
    lines.append("")

    # Findings by category
    findings_by_category: dict[str, list] = {}
    for f in intelligence.findings:
        findings_by_category.setdefault(f.category, []).append(f)

    if findings_by_category:
        lines.append("## Findings")
        lines.append("")
        for category in sorted(findings_by_category.keys()):
            cat_findings = findings_by_category[category]
            lines.append(f"### {category} ({len(cat_findings)})")
            lines.append("")
            for f in cat_findings:
                lines.append(f"- **[{f.severity.upper()}]** `{f.finding_id}`: {f.title}")
                lines.append(f"  - Confidence: {f.confidence:.0%}")
                lines.append(f"  - {f.explanation}")
                if f.evidence_references:
                    for ev in f.evidence_references:
                        lines.append(f"  - Evidence: `{ev.reference_path}` — {ev.detail}")
            lines.append("")

    # Recommendations
    if intelligence.recommendations:
        lines.append("## Recommendations")
        lines.append("")
        for r in intelligence.recommendations:
            lines.append(f"- **{r.finding_id}**: {r.recommendation}")
            lines.append(f"  - Rationale: {r.rationale}")
            lines.append(f"  - Priority: {r.priority.score}/10 (impact={r.priority.impact}, severity={r.priority.severity})")
            lines.append(f"  - Effort: {r.estimated_effort} | Risk: {r.estimated_risk}")
            lines.append(f"  - Benefit: {r.expected_benefit}")
        lines.append("")

    # Candidate Missions
    if intelligence.candidate_missions:
        lines.append("## Candidate Missions")
        lines.append("")
        for m in intelligence.candidate_missions:
            lines.append(f"### {m.mission_id}: {m.title}")
            lines.append("")
            lines.append(f"- **Type:** {m.mission_type}")
            lines.append(f"- **Objective:** {m.objective}")
            lines.append(f"- **Effort:** {m.estimated_effort}")
            lines.append(f"- **Priority:** {m.priority.score}/10")
            lines.append(f"- **Risk:** {m.risk.level}")
            lines.append(f"- **Affected modules:** {len(m.affected_modules)}")
            lines.append(f"- **Supporting findings:** {', '.join(m.supporting_findings)}")
            if m.prerequisites:
                lines.append(f"- **Prerequisites:** {', '.join(m.prerequisites)}")
            lines.append("")

    return "\n".join(lines)


def save_artifacts(
    intelligence: EngineeringIntelligence,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Save JSON and Markdown artifacts atomically."""
    from .utils import atomic_write_json

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "ENGINEERING_INTELLIGENCE.json"
    md_path = output_dir / "ENGINEERING_INTELLIGENCE.md"

    # JSON (authoritative)
    atomic_write_json(json_path, intelligence.as_dict())

    # Markdown (derived from same model)
    md_content = render_markdown(intelligence)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
