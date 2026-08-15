"""Enterprise → EVOSIA Core integration bridge.

Orchestrates real EVOSIA Core pipeline stages for Enterprise scan jobs.
Contains integration/orchestration logic only — no duplicate analysis rules.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def materialize_repository(
    identifier: str,
    ref: str | None = None,
    depth: int = 1,
) -> tuple[Path, str]:
    """Clone a GitHub repository to a temporary directory.

    Returns (path, commit_sha).
    """
    from evosia.github_provider import GitHubRepositoryProvider

    provider = GitHubRepositoryProvider()
    target = Path(tempfile.mkdtemp(prefix="hermes-materialize-"))
    try:
        result_path = provider.materialize(identifier, target, ref=ref, depth=depth)
        commit_file = result_path / ".hermes-commit"
        commit_sha = commit_file.read_text().strip() if commit_file.exists() else ""
        return result_path, commit_sha
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def dispose_materialized(path: Path) -> None:
    """Clean up a materialized repository directory."""
    if path.exists() and path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def run_readiness(repo_path: Path) -> dict[str, Any]:
    """Run real Repository Readiness assessment."""
    from evosia.readiness import assess_readiness
    result = assess_readiness(repo_path)
    return result.as_dict()


def run_repository_intelligence(repo_root: Path) -> dict[str, Any]:
    """Run real Repository Intelligence scanner."""
    from evosia.repo_scanner import scan_repository
    return scan_repository(repo_root)


def run_engineering_intelligence(ri: dict[str, Any]) -> dict[str, Any]:
    """Run real Engineering Intelligence analysis."""
    from evosia.engineering_analyzer import analyze_engineering
    result = analyze_engineering(ri)
    return result.as_dict()


def run_governance(ei: dict[str, Any]) -> dict[str, Any]:
    """Run real Engineering Governance analysis."""
    from evosia.governance_analyzer import govern_engineering
    result = govern_engineering(ei)
    return result.as_dict()


def run_mission_recommendation(governance: dict[str, Any]) -> dict[str, Any]:
    """Run real Mission Recommendation generation."""
    from evosia.mission_generator import generate_missions
    result = generate_missions(governance)
    return result.as_dict()


def normalize_findings(ei_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract findings from Engineering Intelligence for Enterprise persistence."""
    findings = []
    for f in ei_dict.get("findings", []):
        findings.append({
            "finding_type": f.get("category", "unknown"),
            "severity": f.get("severity", "info"),
            "category": f.get("category", "general"),
            "title": f.get("title", ""),
            "description": f.get("explanation", ""),
            "module": _extract_module(f),
            "priority_score": _extract_priority_score(f),
            "effort": _extract_effort(f),
            "evidence_references": f.get("evidence_references", []),
            "affected_components": f.get("affected_components", []),
        })
    return findings


def normalize_recommendations(ei_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract recommendations from Engineering Intelligence."""
    recs = []
    for r in ei_dict.get("recommendations", []):
        recs.append({
            "finding_id": r.get("finding_id", ""),
            "recommendation": r.get("recommendation", ""),
            "rationale": r.get("rationale", ""),
            "priority_score": r.get("priority", {}).get("score", 0) if isinstance(r.get("priority"), dict) else 0,
            "estimated_effort": r.get("estimated_effort", ""),
            "estimated_risk": r.get("estimated_risk", ""),
            "expected_benefit": r.get("expected_benefit", ""),
        })
    return recs


def normalize_governance_decisions(gov_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract governance decisions."""
    decisions = []
    assessment = gov_dict.get("assessment", {})
    for d in assessment.get("approval_decisions", []):
        decisions.append({
            "finding_id": d.get("finding_id", ""),
            "decision": d.get("decision", ""),
            "rationale": d.get("rationale", ""),
            "conditions": d.get("conditions", []),
        })
    return decisions


def normalize_missions(missions_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract draft missions from Mission Recommendations."""
    missions = []
    for m in missions_dict.get("draft_missions", []):
        missions.append({
            "mission_id": m.get("mission_id", ""),
            "title": m.get("title", ""),
            "description": m.get("description", ""),
            "objective": m.get("objective", ""),
            "mission_type": m.get("mission_type", ""),
            "estimated_effort": m.get("estimated_effort", ""),
            "priority_score": m.get("priority_score", 0),
            "state": m.get("state", "DRAFT"),
            "originating_finding_id": m.get("originating_finding_id", ""),
            "originating_recommendation": m.get("originating_recommendation", ""),
        })
    return missions


def _extract_module(finding: dict[str, Any]) -> str | None:
    components = finding.get("affected_components", [])
    if components and isinstance(components, list) and len(components) > 0:
        c = components[0]
        if isinstance(c, dict):
            return c.get("component_path") or c.get("component_name")
    return None


def _extract_priority_score(finding: dict[str, Any]) -> float | None:
    return finding.get("priority_score")


def _extract_effort(finding: dict[str, Any]) -> str | None:
    return finding.get("estimated_effort")
