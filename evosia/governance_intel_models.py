"""Engineering Governance — data models.

Frozen dataclasses for evaluating engineering recommendations before
they become executable missions. Every field is immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceQuality:
    """Evaluates the quality of evidence behind a recommendation."""

    level: str             # "low", "medium", "high"
    reference_count: int   # number of evidence references
    diversity: str         # "single_source", "limited", "diverse"
    consistency: str       # "inconsistent", "partial", "consistent"
    reasoning: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "reference_count": self.reference_count,
            "diversity": self.diversity,
            "consistency": self.consistency,
            "reasoning": self.reasoning,
        }


@dataclass(frozen=True)
class ArchitectureImpact:
    """Estimates the architectural scope of a recommendation."""

    level: str             # "local", "package", "system"
    affected_count: int
    reasoning: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "affected_count": self.affected_count,
            "reasoning": self.reasoning,
        }


@dataclass(frozen=True)
class Conflict:
    """Detects recommendations that cannot both be true."""

    conflict_id: str       # "CONFLICT-001"
    recommendation_a: str  # finding_id
    recommendation_b: str  # finding_id
    description: str
    severity: str          # "low", "medium", "high"

    def as_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "recommendation_a": self.recommendation_a,
            "recommendation_b": self.recommendation_b,
            "description": self.description,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class DuplicateRecommendation:
    """Detects recommendations that describe the same engineering work."""

    duplicate_id: str      # "DUP-001"
    primary: str           # finding_id of the kept recommendation
    duplicate: str         # finding_id of the merged recommendation
    similarity: str        # "identical", "overlapping", "redundant"
    reasoning: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "duplicate_id": self.duplicate_id,
            "primary": self.primary,
            "duplicate": self.duplicate,
            "similarity": self.similarity,
            "reasoning": self.reasoning,
        }


@dataclass(frozen=True)
class RecommendationAssessment:
    """Evaluates a single recommendation across multiple dimensions."""

    finding_id: str
    evidence_quality: EvidenceQuality
    completeness: str      # "complete", "partial", "insufficient"
    architectural_consistency: str  # "consistent", "inconsistent", "neutral"
    duplication: str       # "unique", "duplicate", "primary"
    scope: str             # "local", "package", "system"
    expected_impact: str   # "low", "medium", "high"
    risk_level: str        # "none", "low", "medium", "high"
    confidence: float      # 0.0–1.0
    notes: str             # optional governance notes

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "evidence_quality": self.evidence_quality.as_dict(),
            "completeness": self.completeness,
            "architectural_consistency": self.architectural_consistency,
            "duplication": self.duplication,
            "scope": self.scope,
            "expected_impact": self.expected_impact,
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 2),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ApprovalDecision:
    """Exactly one decision per recommendation."""

    finding_id: str
    decision: str          # "APPROVED", "APPROVED_WITH_NOTES", "NEEDS_MORE_EVIDENCE", "DEFERRED", "REJECTED"
    rationale: str
    conditions: tuple[str, ...]  # conditions for approval or reasons for rejection

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "decision": self.decision,
            "rationale": self.rationale,
            "conditions": list(self.conditions),
        }


@dataclass(frozen=True)
class ApprovedCandidateMission:
    """An approved recommendation ready for mission planning."""

    finding_id: str
    recommendation: str
    priority_score: float
    effort: str
    risk: str
    mission_type: str
    affected_modules: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "recommendation": self.recommendation,
            "priority_score": round(self.priority_score, 2),
            "effort": self.effort,
            "risk": self.risk,
            "mission_type": self.mission_type,
            "affected_modules": list(self.affected_modules),
        }


# ---------------------------------------------------------------------------
# Evidence & Risk Gate — machine-authority states (Post Cycle 8)
# ---------------------------------------------------------------------------

# Gate (machine) vocabulary. These states NEVER imply human actionability.
GATE_OBSERVED = "OBSERVED"
GATE_CORROBORATED = "CORROBORATED"
GATE_REQUIRES_REVIEW = "REQUIRES_REVIEW"
GATE_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
GATE_DEFERRED = "DEFERRED"
GATE_DUPLICATE = "DUPLICATE"
GATE_LEGACY_APPROVED = "LEGACY_APPROVED"
GATE_LEGACY_REJECTED = "LEGACY_REJECTED"

# Human-authority vocabulary (NEVER emitted by machine gate logic).
HUMAN_ACTIONABLE = "ACTIONABLE"
HUMAN_NOT_ACTIONABLE = "NOT_ACTIONABLE"
HUMAN_NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
HUMAN_DUPLICATE = "DUPLICATE"

# The machine gate may never produce these strings as a gate/decision state.
_FORBIDDEN_MACHINE_STATES = frozenset({HUMAN_ACTIONABLE, HUMAN_NOT_ACTIONABLE})


def assert_machine_state(state: str) -> None:
    """Guard: machine gate logic must never emit human-actionability states."""
    if state in _FORBIDDEN_MACHINE_STATES:
        raise ValueError(
            f"Machine gate may not emit human-authority state {state!r}. "
            f"Actionability requires human adjudication."
        )


@dataclass(frozen=True)
class FindingGate:
    """Evidence & Risk Gate routing for a single finding (machine authority).

    This is the replacement for automated APPROVED semantics. It records what
    EVOSIA observed and whether human review is required — never whether a
    human should act.
    """

    finding_id: str
    observation_state: str     # OBSERVED | CORROBORATED
    gate_state: str            # REQUIRES_REVIEW | INSUFFICIENT_EVIDENCE | DEFERRED | DUPLICATE
    risk_band: str             # LOW | MODERATE | HIGH
    evidence_sufficiency: str  # SUFFICIENT | INSUFFICIENT
    review_rank: float         # evidence/risk ranking (uncertainty explicit)
    uncertainty_note: str      # always present
    evidence_references: tuple[dict[str, Any], ...] = ()
    legacy_decision: str | None = None  # original APPROVED/REJECTED if from migration

    def __post_init__(self) -> None:
        assert_machine_state(self.gate_state)
        assert_machine_state(self.observation_state)

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "observation_state": self.observation_state,
            "gate_state": self.gate_state,
            "risk_band": self.risk_band,
            "evidence_sufficiency": self.evidence_sufficiency,
            "review_rank": round(self.review_rank, 4),
            "uncertainty_note": self.uncertainty_note,
            "evidence_references": [e for e in self.evidence_references],
            "legacy_decision": self.legacy_decision,
            "authority": "machine_gate",
        }


@dataclass(frozen=True)
class GovernanceAssessment:
    """Complete governance evaluation of engineering recommendations."""

    recommendation_assessments: tuple[RecommendationAssessment, ...]
    approval_decisions: tuple[ApprovalDecision, ...]
    conflicts: tuple[Conflict, ...]
    duplicates: tuple[DuplicateRecommendation, ...]
    approved_missions: tuple[ApprovedCandidateMission, ...]
    summary: ApprovalSummary
    gate_routings: tuple[FindingGate, ...] = ()  # Evidence & Risk Gate (Post Cycle 8)

    def as_dict(self) -> dict[str, Any]:
        return {
            "recommendation_assessments": [r.as_dict() for r in self.recommendation_assessments],
            "approval_decisions": [d.as_dict() for d in self.approval_decisions],
            "conflicts": [c.as_dict() for c in self.conflicts],
            "duplicates": [d.as_dict() for d in self.duplicates],
            "approved_missions": [m.as_dict() for m in self.approved_missions],
            "gate_routings": [g.as_dict() for g in self.gate_routings],
            "summary": self.summary.as_dict(),
        }


@dataclass(frozen=True)
class ApprovalSummary:
    """Executive summary of governance decisions."""

    total_evaluated: int
    approved: int
    approved_with_notes: int
    needs_more_evidence: int
    deferred: int
    rejected: int
    conflicts_found: int
    duplicates_found: int
    approval_rate: float   # 0.0–1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "approved": self.approved,
            "approved_with_notes": self.approved_with_notes,
            "needs_more_evidence": self.needs_more_evidence,
            "deferred": self.deferred,
            "rejected": self.rejected,
            "conflicts_found": self.conflicts_found,
            "duplicates_found": self.duplicates_found,
            "approval_rate": round(self.approval_rate, 2),
        }


class EngineeringGovernance:
    """Top-level governance model.

    NOT frozen because it uses field(default_factory=...).
    """

    def __init__(
        self,
        *,
        repository: dict[str, Any] | None = None,
        assessment: GovernanceAssessment | None = None,
        schema_version: str = "1",
    ) -> None:
        self.schema_version = schema_version
        self.repository = repository or {}
        self.assessment = assessment or GovernanceAssessment(
            recommendation_assessments=(),
            approval_decisions=(),
            conflicts=(),
            duplicates=(),
            approved_missions=(),
            summary=ApprovalSummary(
                total_evaluated=0,
                approved=0,
                approved_with_notes=0,
                needs_more_evidence=0,
                deferred=0,
                rejected=0,
                conflicts_found=0,
                duplicates_found=0,
                approval_rate=0.0,
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "assessment": self.assessment.as_dict(),
        }
