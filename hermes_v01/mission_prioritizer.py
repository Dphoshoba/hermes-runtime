"""Mission Prioritization — evidence-based mission ranking and selection.

Replaces arbitrary finding-ID ordering with deterministic,
evidence-based mission prioritization while retaining the existing
50-mission-per-repository safety/attention cap.

Pipeline concept:
    Finding
    → Governance
    → Candidate Mission
    → Mission Prioritization  ← THIS COMPONENT
    → Attention Cap
    → Persisted Draft Mission

Product Principle:
    The goal is NOT "generate as many missions as possible."
    The goal is "surface the smallest number of missions containing
    the greatest evidence-supported engineering value."

Detection vs Prioritization:
    A valid observation does not automatically deserve operator attention.
    Detection and prioritization are separate concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Priority Bands
# ---------------------------------------------------------------------------

PRIORITY_BANDS = {
    "P0_CRITICAL": 15.0,
    "P1_HIGH": 10.0,
    "P2_MEDIUM": 5.0,
    "P3_LOW": 0.0,
    "P4_REVIEW_REQUIRED": float("-inf"),
}


def _priority_band_from_score(score: float) -> str:
    """Map priority score to priority band."""
    if score >= PRIORITY_BANDS["P0_CRITICAL"]:
        return "P0_CRITICAL"
    elif score >= PRIORITY_BANDS["P1_HIGH"]:
        return "P1_HIGH"
    elif score >= PRIORITY_BANDS["P2_MEDIUM"]:
        return "P2_MEDIUM"
    elif score >= PRIORITY_BANDS["P3_LOW"]:
        return "P3_LOW"
    else:
        return "P4_REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Severity Ranking (for tie-breaking)
# ---------------------------------------------------------------------------

SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PriorityReason:
    """A single reason contributing to a mission's priority score."""

    factor: str
    weight: float
    description: str


@dataclass
class MissionPriority:
    """Complete priority assessment for a single mission."""

    mission_id: str
    priority_score: float
    priority_band: str
    priority_reasons: tuple[PriorityReason, ...]
    priority_rank: int | None = None
    selection_status: str = "PENDING"


@dataclass
class PrioritizationResult:
    """Result of mission prioritization."""

    selected: list[MissionPriority]
    deferred: list[MissionPriority]
    suppressed: list[MissionPriority]
    candidate_count: int
    selected_count: int
    deferred_count: int
    suppressed_count: int
    cap: int
    repository: str | None = None


# ---------------------------------------------------------------------------
# Priority Scoring
# ---------------------------------------------------------------------------

# Human classification weights (authoritative operator evidence)
_HUMAN_WEIGHTS = {
    "USEFUL": 10.0,
    "NOT_ACTIONABLE": -10.0,
    "FALSE_POSITIVE": -10.0,
    "DUPLICATE": -10.0,
    "NEEDS_MORE_EVIDENCE": -2.0,
    "UNREVIEWED": 0.0,
    "UNKNOWN": 0.0,
}

# Severity weights
_SEVERITY_WEIGHTS = {
    "critical": 10.0,
    "high": 7.5,
    "medium": 5.0,
    "low": 2.5,
    "info": 1.0,
}

# Evidence quality weights
_EVIDENCE_WEIGHTS = {
    "diverse": 3.0,
    "limited": 2.0,
    "single": 1.0,
    "none": 0.0,
}

# Governance decision weights
_GOVERNANCE_WEIGHTS = {
    "APPROVED": 2.0,
    "APPROVED_WITH_NOTES": 1.0,
    "NEEDS_MORE_EVIDENCE": 0.0,
    "DEFERRED": -1.0,
    "REJECTED": -2.0,
    "UNKNOWN": 0.0,
}

# Context penalties
_CONTEXT_PENALTIES = {
    "test": -1.0,
    "configuration": -0.5,
    "setup": -0.5,
    "production": 0.0,
    "other": 0.0,
}


def _compute_evidence_quality(evidence_references: list[dict[str, Any]]) -> tuple[float, str]:
    """Compute evidence quality score from evidence references."""
    if not evidence_references:
        return 0.0, "none"

    sources = {e.get("source", "") for e in evidence_references}
    n_refs = len(evidence_references)
    n_sources = len(sources)

    if n_sources >= 3:
        return _EVIDENCE_WEIGHTS["diverse"], "diverse"
    elif n_sources >= 2 or n_refs >= 2:
        return _EVIDENCE_WEIGHTS["limited"], "limited"
    elif n_refs >= 1:
        return _EVIDENCE_WEIGHTS["single"], "single"
    else:
        return _EVIDENCE_WEIGHTS["none"], "none"


def _compute_context_penalty(file_context: str) -> tuple[float, str]:
    """Compute context penalty from file path."""
    ctx_lower = file_context.lower()

    if "test" in ctx_lower:
        return _CONTEXT_PENALTIES["test"], "test"
    elif "config" in ctx_lower or "setup" in ctx_lower:
        return _CONTEXT_PENALTIES["configuration"], "configuration"
    elif ctx_lower.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
        return _CONTEXT_PENALTIES["production"], "production"
    else:
        return _CONTEXT_PENALTIES["other"], "other"


def _get_human_classification(mission: dict[str, Any]) -> str:
    """Extract human classification from mission or its finding."""
    # Check mission-level human_classification first
    human_cls = mission.get("human_classification", "UNKNOWN")
    if human_cls and human_cls != "UNKNOWN":
        return human_cls

    # Check finding-level human_classification
    finding = mission.get("finding", {})
    if isinstance(finding, dict):
        human_cls = finding.get("human_classification", "UNKNOWN")
        if human_cls and human_cls != "UNKNOWN":
            return human_cls

    return "UNKNOWN"


def compute_priority_score(mission: dict[str, Any]) -> tuple[float, list[PriorityReason]]:
    """
    Compute priority score for a mission using only evidence already available.

    Scoring formula:
        Score = Human Classification Bonus
              + Severity Score
              + Evidence Quality Bonus
              + Governance Decision Bonus
              + Context Penalty

    Every score must be reconstructable from persisted inputs.
    No repository-specific exceptions, hidden weights, or random ordering.
    """
    reasons: list[PriorityReason] = []
    score = 0.0

    # 1. Human classification (authoritative operator evidence)
    human_cls = _get_human_classification(mission)
    human_weight = _HUMAN_WEIGHTS.get(human_cls, 0.0)
    score += human_weight
    if human_weight != 0.0:
        reasons.append(PriorityReason(
            factor="human_classification",
            weight=human_weight,
            description=f"Human {human_cls} ({human_weight:+.1f})",
        ))

    # 2. Severity
    severity = mission.get("finding_severity", "low")
    sev_weight = _SEVERITY_WEIGHTS.get(severity, 1.0)
    score += sev_weight
    reasons.append(PriorityReason(
        factor="severity",
        weight=sev_weight,
        description=f"Severity {severity} ({sev_weight:+.1f})",
    ))

    # 3. Evidence quality
    evidence_refs = mission.get("evidence_references", [])
    ev_score, ev_quality = _compute_evidence_quality(evidence_refs)
    score += ev_score
    if ev_score > 0.0:
        reasons.append(PriorityReason(
            factor="evidence_quality",
            weight=ev_score,
            description=f"Evidence {ev_quality} ({ev_score:+.1f})",
        ))

    # 4. Governance decision
    gov_decision = mission.get("governance_decision", "UNKNOWN")
    gov_weight = _GOVERNANCE_WEIGHTS.get(gov_decision, 0.0)
    score += gov_weight
    if gov_weight != 0.0:
        reasons.append(PriorityReason(
            factor="governance_decision",
            weight=gov_weight,
            description=f"Governance {gov_decision} ({gov_weight:+.1f})",
        ))

    # 5. Context penalty
    file_context = mission.get("file_context", "")
    ctx_penalty, ctx_type = _compute_context_penalty(file_context)
    score += ctx_penalty
    if ctx_penalty != 0.0:
        reasons.append(PriorityReason(
            factor="context_penalty",
            weight=ctx_penalty,
            description=f"Context {ctx_type} ({ctx_penalty:+.1f})",
        ))

    return round(score, 2), tuple(reasons)


# ---------------------------------------------------------------------------
# Deterministic Tie-Breaking
# ---------------------------------------------------------------------------

def _tie_break_key(mp: MissionPriority, mission: dict[str, Any]) -> tuple:
    """
    Deterministic tie-breaking key for missions with equal priority scores.

    Tie-breaking order:
        1. Priority score DESC
        2. Severity rank DESC
        3. Evidence strength DESC (number of evidence references)
        4. Finding ID ASC (stable identity)
    """
    severity = mission.get("finding_severity", "low")
    sev_rank = SEVERITY_RANK.get(severity, 0)
    evidence_count = len(mission.get("evidence_references", []))
    finding_id = mission.get("originating_finding_id", mission.get("mission_id", ""))

    return (
        -mp.priority_score,  # DESC
        -sev_rank,           # DESC
        -evidence_count,     # DESC
        finding_id,          # ASC (stable)
    )


# ---------------------------------------------------------------------------
# Selection Status Determination
# ---------------------------------------------------------------------------

def _determine_selection_status(
    human_cls: str,
    rank: int | None,
    cap: int,
) -> str:
    """Determine selection status based on human classification and rank."""
    if human_cls == "FALSE_POSITIVE":
        return "SUPPRESSED_FALSE_POSITIVE"
    elif human_cls == "DUPLICATE":
        return "SUPPRESSED_DUPLICATE"
    elif human_cls == "NOT_ACTIONABLE":
        return "SUPPRESSED_NON_ACTIONABLE"
    elif rank is not None and rank > cap:
        return "DEFERRED_BY_PRIORITY_CAP"
    elif rank is not None and rank <= cap:
        return "SELECTED"
    else:
        return "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Main Prioritization Function
# ---------------------------------------------------------------------------

def prioritize_missions(
    missions: Sequence[dict[str, Any]],
    limit: int = 50,
    repository: str | None = None,
) -> PrioritizationResult:
    """
    Prioritize missions using evidence-based scoring.

    Args:
        missions: List of mission dictionaries to prioritize
        limit: Maximum number of missions to select (default: 50)
        repository: Repository name for tracking

    Returns:
        PrioritizationResult with selected, deferred, and suppressed missions

    This function:
        1. Computes priority score for each mission
        2. Ranks missions deterministically
        3. Applies 50-mission attention cap
        4. Preserves deferred missions for auditability
        5. Maintains 100% traceability
    """
    if not missions:
        return PrioritizationResult(
            selected=[],
            deferred=[],
            suppressed=[],
            candidate_count=0,
            selected_count=0,
            deferred_count=0,
            suppressed_count=0,
            cap=limit,
            repository=repository,
        )

    # Phase 1: Compute priority scores
    mission_priorities: list[tuple[dict[str, Any], MissionPriority]] = []

    for mission in missions:
        score, reasons = compute_priority_score(mission)
        band = _priority_band_from_score(score)

        mp = MissionPriority(
            mission_id=mission.get("mission_id", ""),
            priority_score=score,
            priority_band=band,
            priority_reasons=reasons,
            selection_status="PENDING",
        )
        mission_priorities.append((mission, mp))

    # Phase 2: Sort by priority (deterministic tie-breaking)
    mission_priorities.sort(key=lambda x: _tie_break_key(x[1], x[0]))

    # Phase 3: Assign ranks
    for rank_idx, (mission, mp) in enumerate(mission_priorities, 1):
        mp.priority_rank = rank_idx

    # Phase 4: Determine selection status
    selected: list[MissionPriority] = []
    deferred: list[MissionPriority] = []
    suppressed: list[MissionPriority] = []

    for mission, mp in mission_priorities:
        human_cls = _get_human_classification(mission)
        mp.selection_status = _determine_selection_status(human_cls, mp.priority_rank, limit)

        if mp.selection_status == "SELECTED":
            selected.append(mp)
        elif mp.selection_status.startswith("SUPPRESSED_"):
            suppressed.append(mp)
        elif mp.selection_status == "DEFERRED_BY_PRIORITY_CAP":
            deferred.append(mp)
        else:
            # REVIEW_REQUIRED or other
            if mp.priority_rank and mp.priority_rank <= limit:
                selected.append(mp)
                mp.selection_status = "SELECTED"
            else:
                deferred.append(mp)
                mp.selection_status = "DEFERRED_BY_PRIORITY_CAP"

    return PrioritizationResult(
        selected=selected,
        deferred=deferred,
        suppressed=suppressed,
        candidate_count=len(missions),
        selected_count=len(selected),
        deferred_count=len(deferred),
        suppressed_count=len(suppressed),
        cap=limit,
        repository=repository,
    )


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------

def mission_priority_to_dict(mp: MissionPriority) -> dict[str, Any]:
    """Convert MissionPriority to dictionary for serialization."""
    return {
        "mission_id": mp.mission_id,
        "priority_score": mp.priority_score,
        "priority_band": mp.priority_band,
        "priority_reasons": [
            {
                "factor": r.factor,
                "weight": r.weight,
                "description": r.description,
            }
            for r in mp.priority_reasons
        ],
        "priority_rank": mp.priority_rank,
        "selection_status": mp.selection_status,
    }


def prioritization_result_to_dict(result: PrioritizationResult) -> dict[str, Any]:
    """Convert PrioritizationResult to dictionary for serialization."""
    return {
        "candidate_count": result.candidate_count,
        "selected_count": result.selected_count,
        "deferred_count": result.deferred_count,
        "suppressed_count": result.suppressed_count,
        "cap": result.cap,
        "repository": result.repository,
        "selected": [mission_priority_to_dict(mp) for mp in result.selected],
        "deferred": [mission_priority_to_dict(mp) for mp in result.deferred],
        "suppressed": [mission_priority_to_dict(mp) for mp in result.suppressed],
    }
