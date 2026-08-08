"""Engineering Intelligence — data models.

Frozen dataclasses for evidence-based engineering recommendations.
Every field is immutable. All collections are tuples for determinism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceReference:
    """Links a finding to specific Repository Intelligence data."""

    source: str          # "complexity_signals", "debt_signals", "module_graph", "tests", "dependencies", "public_api", "configuration"
    reference_path: str  # "hermes_v01/mission.py" or "hermes_v01/mission.py::MissionRunner"
    detail: str          # "Module has 814 lines"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reference_path": self.reference_path,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class AffectedComponent:
    """Identifies what part of the repository is affected."""

    component_type: str  # "module", "class", "function", "dependency", "configuration", "cli", "test"
    component_path: str  # "hermes_v01/mission.py"
    component_name: str  # "mission.py" or "MissionRunner"

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "component_path": self.component_path,
            "component_name": self.component_name,
        }


@dataclass(frozen=True)
class PriorityScore:
    """Quantified priority with documented scoring formula.

    Formula: 0.40*impact + 0.20*(confidence*10) + 0.25*severity + 0.15*scope
    All components normalized to 0.0–10.0 scale.
    """

    score: float         # 0.0–10.0, composite
    impact: float        # 0.0–10.0
    confidence: float    # 0.0–1.0
    severity: float      # 0.0–10.0
    scope: float         # 0.0–10.0
    formula: str         # "0.40*impact + 0.20*(confidence*10) + 0.25*severity + 0.15*scope"

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "impact": round(self.impact, 2),
            "confidence": round(self.confidence, 2),
            "severity": round(self.severity, 2),
            "scope": round(self.scope, 2),
            "formula": self.formula,
        }


@dataclass(frozen=True)
class ConfidenceScore:
    """How confident we are in an analysis, with basis and limitations."""

    score: float         # 0.0–1.0
    basis: str           # "multiple complexity signals converge"
    limitations: str     # "analysis based on AST only, no runtime data"

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "basis": self.basis,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class RiskAssessment:
    """Repository-level or mission-level risk assessment."""

    level: str             # "low", "moderate", "high", "critical"
    reasoning: str
    evidence: tuple[str, ...]
    mitigation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "reasoning": self.reasoning,
            "evidence": list(self.evidence),
            "mitigation": self.mitigation,
        }


@dataclass(frozen=True)
class Finding:
    """A specific observation derived from repository evidence.

    Every finding must have at least one evidence reference.
    No finding may exist without repository evidence.
    """

    finding_id: str                          # "FINDING-001"
    category: str                            # one of 15 categories
    severity: str                            # "info", "low", "medium", "high", "critical"
    confidence: float                        # 0.0–1.0
    title: str                               # concise description
    explanation: str                         # detailed reasoning
    evidence_references: tuple[EvidenceReference, ...]
    affected_components: tuple[AffectedComponent, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "severity": self.severity,
            "confidence": round(self.confidence, 2),
            "title": self.title,
            "explanation": self.explanation,
            "evidence_references": [e.as_dict() for e in self.evidence_references],
            "affected_components": [c.as_dict() for c in self.affected_components],
        }


@dataclass(frozen=True)
class Recommendation:
    """What should be done about a finding."""

    finding_id: str
    recommendation: str
    rationale: str
    priority: PriorityScore
    estimated_effort: str    # "trivial", "small", "medium", "large", "xl"
    estimated_risk: str      # "none", "low", "medium", "high"
    expected_benefit: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "priority": self.priority.as_dict(),
            "estimated_effort": self.estimated_effort,
            "estimated_risk": self.estimated_risk,
            "expected_benefit": self.expected_benefit,
        }


@dataclass(frozen=True)
class CandidateMission:
    """A mission that could address findings. NOT enqueued."""

    mission_id: str                          # "MISSION-001"
    title: str
    description: str
    objective: str
    affected_modules: tuple[str, ...]
    estimated_effort: str
    priority: PriorityScore
    risk: RiskAssessment
    prerequisites: tuple[str, ...]
    supporting_findings: tuple[str, ...]
    mission_type: str   # "repository_maintenance", "documentation_refresh", etc.

    def as_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "title": self.title,
            "description": self.description,
            "objective": self.objective,
            "affected_modules": list(self.affected_modules),
            "estimated_effort": self.estimated_effort,
            "priority": self.priority.as_dict(),
            "risk": self.risk.as_dict(),
            "prerequisites": list(self.prerequisites),
            "supporting_findings": list(self.supporting_findings),
            "mission_type": self.mission_type,
        }


@dataclass(frozen=True)
class EngineeringSummary:
    """Executive summary counts and health score."""

    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    total_recommendations: int
    total_candidate_missions: int
    overall_risk: str
    health_score: float    # 0.0–100.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "total_recommendations": self.total_recommendations,
            "total_candidate_missions": self.total_candidate_missions,
            "overall_risk": self.overall_risk,
            "health_score": round(self.health_score, 1),
        }


class EngineeringIntelligence:
    """Top-level engineering intelligence model.

    NOT frozen because it uses field(default_factory=...).
    """

    def __init__(
        self,
        *,
        repository: dict[str, Any] | None = None,
        findings: tuple[Finding, ...] = (),
        recommendations: tuple[Recommendation, ...] = (),
        candidate_missions: tuple[CandidateMission, ...] = (),
        risk_assessment: RiskAssessment | None = None,
        summary: EngineeringSummary | None = None,
        schema_version: str = "1",
    ) -> None:
        self.schema_version = schema_version
        self.repository = repository or {}
        self.findings = findings
        self.recommendations = recommendations
        self.candidate_missions = candidate_missions
        self.risk_assessment = risk_assessment or RiskAssessment(
            level="low",
            reasoning="No findings",
            evidence=(),
            mitigation="No action required",
        )
        self.summary = summary or EngineeringSummary(
            total_findings=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            info_count=0,
            total_recommendations=0,
            total_candidate_missions=0,
            overall_risk="low",
            health_score=100.0,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "findings": [f.as_dict() for f in self.findings],
            "recommendations": [r.as_dict() for r in self.recommendations],
            "candidate_missions": [m.as_dict() for m in self.candidate_missions],
            "risk_assessment": self.risk_assessment.as_dict(),
            "summary": self.summary.as_dict(),
        }
