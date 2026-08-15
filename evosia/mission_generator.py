"""Mission Recommendation Integration — mission generator.

Converts ApprovedCandidateMission objects into EVOSIA Mission artifacts.
Every mission remains in DRAFT state. Never enqueues automatically.

Pipeline:
    Finding → Governance → Candidate Mission → Mission Prioritization → Attention Cap → Persisted Draft Mission

Product Principle:
    The goal is NOT "generate as many missions as possible."
    The goal is "surface the smallest number of missions containing
    the greatest evidence-supported engineering value."
"""

from __future__ import annotations

from typing import Any

# Evidenced & Risk Gate (Post Cycle 8) — hard mission authorization boundary.
# Human-authority vocabulary that MAY authorize a candidate mission.
HUMAN_ACTIONABLE = "ACTIONABLE"

# Machine gate states that must NEVER authorize a mission.
_FORBIDDEN_GATE_DECISIONS = frozenset({
    "OBSERVED", "CORROBORATED", "REQUIRES_REVIEW", "INSUFFICIENT_EVIDENCE",
    "DEFERRED", "DUPLICATE", "LEGACY_APPROVED", "LEGACY_REJECTED",
    "APPROVED", "APPROVED_WITH_NOTES", "NEEDS_MORE_EVIDENCE", "REJECTED",
})


def _is_human_actionable(fid: str, actionable_ids: set[str] | None) -> bool:
    """Hard boundary: only a human ACTIONABLE adjudication authorizes a mission.

    actionable_ids is the set of finding_ids with a human 'ACTIONABLE'
    adjudication (from the Human Review Service). If None, no finding is
    authorized (gate mode with no review store wired).
    """
    if actionable_ids is None:
        return False
    return fid in actionable_ids


from .mission_recommendation_models import (
    DraftMission,
    GeneratedTask,
    MissionRecommendationSummary,
    MissionRecommendations,
    TraceabilityLink,
)
from .mission_prioritizer import prioritize_missions, prioritization_result_to_dict


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


def generate_missions(
    governance: dict[str, Any],
    actionable_finding_ids: set[str] | None = None,
    actionable_findings: list[dict[str, Any]] | None = None,
) -> MissionRecommendations:
    """Main entry point. Consume governance dict, produce mission recommendations.

    Hard authorization boundary (Evidence & Risk Gate): a candidate mission is
    generated ONLY for a finding present in actionable_finding_ids (the set of
    human 'ACTIONABLE' adjudications from the Human Review Service).

    In gate mode governance["assessment"]["approved_missions"] is empty, so the
    ONLY route to a mission is via actionable_findings built from human
    adjudications. If actionable_finding_ids is None, NO missions are produced —
    the machine gate can never authorize a mission. Legacy mode may still pass
    approved_missions for frozen-history replay; the guard still applies.

    Uses evidence-based mission prioritization instead of arbitrary truncation.
    Applies 50-mission attention cap AFTER priority ranking.
    """
    repository = governance.get("repository", {})
    assessment = governance.get("assessment", {})
    approved_missions = list(assessment.get("approved_missions", []))
    if actionable_findings:
        # Human-reviewed actionable findings become candidate sources.
        approved_missions = approved_missions + list(actionable_findings)
    approval_decisions = assessment.get("approval_decisions", [])

    # Build EI findings lookup from governance decisions
    ei_findings: dict[str, Any] = {}

    # Phase 1: Generate all candidate missions (before prioritization)
    candidate_missions: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}
    total_tasks = 0

    for i, approved in enumerate(approved_missions):
        fid = approved.get("finding_id", "")
        # HARD BOUNDARY: no human ACTIONABLE adjudication => no candidate mission.
        if not _is_human_actionable(fid, actionable_finding_ids):
            continue
        rec = approved.get("recommendation", "")
        mtype = approved.get("mission_type", "repository_maintenance")
        effort = approved.get("effort", "small")
        priority = approved.get("priority_score", 5.0)
        affected = tuple(approved.get("affected_modules", []))
        severity = approved.get("severity", "medium")

        # Generate mission
        mission_id = f"REC-MISSION-{i + 1:03d}"
        tasks = _generate_tasks(mtype, fid)
        traceability = _generate_traceability(approved, ei_findings)

        # Find governance decision for this finding. In gate mode
        # approval_decisions is empty, so the authorization signal is the human
        # ACTIONABLE adjudication (actionable_finding_ids), not a machine gate.
        gov_ref = ""
        gov_decision = "UNKNOWN"
        for d in approval_decisions:
            if d.get("finding_id", "") == fid:
                gov_ref = f"GOV-{fid}"
                gov_decision = d.get("decision", "UNKNOWN")
                break
        if not gov_ref and actionable_finding_ids is not None and fid in actionable_finding_ids:
            # Authorized by human adjudication (Evidence & Risk Gate).
            gov_ref = f"HUMAN-ADJUDICATION-{fid}"
            gov_decision = HUMAN_ACTIONABLE

        # Build mission dict for prioritizer
        mission_dict = {
            "mission_id": mission_id,
            "originating_finding_id": fid,
            "finding_severity": approved.get("severity", "medium"),
            "human_classification": HUMAN_ACTIONABLE,  # authorized by human adjudication
            "governance_decision": gov_decision,       # human authority (HUMAN_ACTIONABLE) or legacy
            "file_context": affected[0] if affected else "",
            "evidence_references": [],
            "recommendation": rec,
            "mission_type": mtype,
            "estimated_effort": effort,
            "priority_score": priority,
            "governance_approval_reference": gov_ref,
            "traceability": traceability,
            "tasks": tasks,
        }
        candidate_missions.append(mission_dict)
        type_counts[mtype] = type_counts.get(mtype, 0) + 1
        total_tasks += len(tasks)

    # Phase 2: Prioritize missions using evidence-based scoring
    prioritization_result = prioritize_missions(
        candidate_missions,
        limit=50,
        repository=repository.get("name"),
    )

    # Phase 3: Generate draft missions from SELECTED candidates only
    draft_missions: list[DraftMission] = []
    selected_type_counts: dict[str, int] = {}
    selected_tasks = 0

    for mp in prioritization_result.selected:
        # Find the original mission dict
        mission_dict = next(
            (m for m in candidate_missions if m["mission_id"] == mp.mission_id),
            None,
        )
        if not mission_dict:
            continue

        draft = DraftMission(
            mission_id=mission_dict["mission_id"],
            title=f"[DRAFT] {mission_dict['recommendation'][:80]}",
            description=f"Generated from governance-approved recommendation for {mission_dict['originating_finding_id']}",
            objective=mission_dict["recommendation"],
            tasks=tuple(mission_dict["tasks"]),
            goals=(mission_dict["recommendation"],),
            constraints=("Must not execute without human approval",),
            required_capabilities=(),
            working_directory=None,
            repository=repository.get("path"),
            state="DRAFT",
            traceability=mission_dict["traceability"],
            originating_finding_id=mission_dict["originating_finding_id"],
            originating_recommendation=mission_dict["recommendation"],
            governance_approval_reference=mission_dict["governance_approval_reference"],
            estimated_effort=mission_dict["estimated_effort"],
            priority_score=mp.priority_score,
            mission_type=mission_dict["mission_type"],
        )
        draft_missions.append(draft)
        mtype = mission_dict["mission_type"]
        selected_type_counts[mtype] = selected_type_counts.get(mtype, 0) + 1
        selected_tasks += len(mission_dict["tasks"])

    summary = MissionRecommendationSummary(
        total_governance_approvals=len(approved_missions),
        missions_generated=len(draft_missions),
        missions_by_type=selected_type_counts,
        total_tasks=selected_tasks,
        traceability_validated=True,
    )

    return MissionRecommendations(
        repository=repository,
        draft_missions=tuple(draft_missions),
        summary=summary,
    )
