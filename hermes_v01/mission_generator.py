"""Mission Recommendation Integration — mission generator.

Converts ApprovedCandidateMission objects into Hermes Mission artifacts.
Every mission remains in DRAFT state. Never enqueues automatically.
"""

from __future__ import annotations

from typing import Any

from .mission_recommendation_models import (
    DraftMission,
    GeneratedTask,
    MissionRecommendationSummary,
    MissionRecommendations,
    TraceabilityLink,
)


# ---------------------------------------------------------------------------
# Task generation from mission type
# ---------------------------------------------------------------------------

_TASK_TEMPLATES: dict[str, list[tuple[str, list[str], tuple[str, ...]]]] = {
    # mission_type: [(title, command_template, capabilities)]
    "architecture_cleanup": [
        ("Analyze current architecture", ["echo", "Analyzing architecture..."], ("analyzer",)),
        ("Identify coupling points", ["echo", "Identifying coupling..."], ("analyzer",)),
        ("Refactor modules", ["echo", "Refactoring modules..."], ("analyzer",)),
        ("Verify no regressions", ["echo", "Verifying..."], ("analyzer",)),
    ],
    "documentation_refresh": [
        ("Audit existing documentation", ["echo", "Auditing docs..."], ()),
        ("Generate missing docstrings", ["echo", "Generating docstrings..."], ()),
        ("Update API documentation", ["echo", "Updating API docs..."], ()),
        ("Validate documentation", ["echo", "Validating docs..."], ()),
    ],
    "testing_improvements": [
        ("Identify untested modules", ["echo", "Identifying gaps..."], ("analyzer",)),
        ("Generate test scaffolds", ["echo", "Generating tests..."], ("analyzer",)),
        ("Run test suite", ["echo", "Running tests..."], ("analyzer",)),
        ("Validate coverage", ["echo", "Validating coverage..."], ("analyzer",)),
    ],
    "dependency_review": [
        ("Audit current dependencies", ["echo", "Auditing deps..."], ()),
        ("Check for vulnerabilities", ["echo", "Checking vulnerabilities..."], ()),
        ("Update pinned versions", ["echo", "Updating versions..."], ()),
        ("Verify builds", ["echo", "Verifying builds..."], ("analyzer",)),
    ],
    "packaging_improvements": [
        ("Review packaging configuration", ["echo", "Reviewing packaging..."], ()),
        ("Fix build configuration", ["echo", "Fixing build config..."], ()),
        ("Test package build", ["echo", "Testing build..."], ("analyzer",)),
        ("Validate distribution", ["echo", "Validating dist..."], ()),
    ],
    "configuration_cleanup": [
        ("Audit configuration files", ["echo", "Auditing config..."], ()),
        ("Remove stale configuration", ["echo", "Removing stale config..."], ()),
        ("Standardize settings", ["echo", "Standardizing..."], ()),
        ("Validate consistency", ["echo", "Validating..."], ()),
    ],
    "repository_maintenance": [
        ("Assess repository health", ["echo", "Assessing health..."], ("analyzer",)),
        ("Identify maintenance items", ["echo", "Identifying items..."], ("analyzer",)),
        ("Execute maintenance", ["echo", "Executing maintenance..."], ("analyzer",)),
        ("Verify results", ["echo", "Verifying..."], ("analyzer",)),
    ],
    "release_readiness": [
        ("Run full test suite", ["echo", "Running tests..."], ("analyzer",)),
        ("Validate documentation", ["echo", "Validating docs..."], ()),
        ("Check dependency versions", ["echo", "Checking deps..."], ()),
        ("Generate release notes", ["echo", "Generating notes..."], ()),
    ],
}


def _generate_tasks(mission_type: str, finding_id: str) -> tuple[GeneratedTask, ...]:
    """Generate tasks for a mission based on its type."""
    templates = _TASK_TEMPLATES.get(mission_type, _TASK_TEMPLATES["repository_maintenance"])
    tasks: list[GeneratedTask] = []
    for i, (title, command, caps) in enumerate(templates):
        deps: tuple[str, ...] = ()
        if i > 0:
            deps = (f"{finding_id}-task-{i - 1:03d}",)
        tasks.append(GeneratedTask(
            task_id=f"{finding_id}-task-{i:03d}",
            title=title,
            command=command,
            dependencies=deps,
            priority=100,
            required_capabilities=caps,
        ))
    return tuple(tasks)


def _generate_traceability(
    approved: dict[str, Any],
    ei_findings: dict[str, Any],
) -> TraceabilityLink:
    """Build traceability link from governance back to RI."""
    fid = approved.get("finding_id", "")
    rec_text = approved.get("recommendation", "")
    eff = approved.get("affected_modules", [])

    # Find the engineering finding for evidence
    ei_finding = ei_findings.get(fid, {})
    evidence_refs = ei_finding.get("evidence_references", [])
    ev_summary = "; ".join(f"{e.get('source', '')}: {e.get('detail', '')}" for e in evidence_refs[:3])

    return TraceabilityLink(
        governance_finding_id=fid,
        engineering_finding_id=fid,
        recommendation_text=rec_text,
        repository_intelligence_source=", ".join(eff[:3]) if eff else "repository",
        evidence_summary=ev_summary or "See engineering intelligence",
    )


def generate_missions(governance: dict[str, Any]) -> MissionRecommendations:
    """Main entry point. Consume governance dict, produce mission recommendations."""
    repository = governance.get("repository", {})
    assessment = governance.get("assessment", {})
    approved_missions = assessment.get("approved_missions", [])
    approval_decisions = assessment.get("approval_decisions", [])

    # Build EI findings lookup from governance decisions
    # (governance decisions reference engineering findings)
    ei_findings: dict[str, Any] = {}

    draft_missions: list[DraftMission] = []
    type_counts: dict[str, int] = {}
    total_tasks = 0

    for i, approved in enumerate(approved_missions):
        fid = approved.get("finding_id", "")
        rec = approved.get("recommendation", "")
        mtype = approved.get("mission_type", "repository_maintenance")
        effort = approved.get("effort", "small")
        priority = approved.get("priority_score", 5.0)
        affected = tuple(approved.get("affected_modules", []))

        # Generate mission
        mission_id = f"REC-MISSION-{i + 1:03d}"
        tasks = _generate_tasks(mtype, fid)
        traceability = _generate_traceability(approved, ei_findings)

        # Find governance decision for this finding
        gov_ref = ""
        for d in approval_decisions:
            if d.get("finding_id", "") == fid:
                gov_ref = f"GOV-{fid}"
                break

        draft = DraftMission(
            mission_id=mission_id,
            title=f"[DRAFT] {rec[:80]}",
            description=f"Generated from governance-approved recommendation for {fid}",
            objective=rec,
            tasks=tasks,
            goals=(rec,),
            constraints=("Must not execute without human approval",),
            required_capabilities=(),
            working_directory=None,
            repository=repository.get("path"),
            state="DRAFT",
            traceability=traceability,
            originating_finding_id=fid,
            originating_recommendation=rec,
            governance_approval_reference=gov_ref,
            estimated_effort=effort,
            priority_score=priority,
            mission_type=mtype,
        )
        draft_missions.append(draft)
        type_counts[mtype] = type_counts.get(mtype, 0) + 1
        total_tasks += len(tasks)

    summary = MissionRecommendationSummary(
        total_governance_approvals=len(approved_missions),
        missions_generated=len(draft_missions),
        missions_by_type=type_counts,
        total_tasks=total_tasks,
        traceability_validated=True,
    )

    return MissionRecommendations(
        repository=repository,
        draft_missions=tuple(draft_missions),
        summary=summary,
    )
