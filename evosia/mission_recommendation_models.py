"""Mission Recommendation Integration — data models.

Frozen dataclasses for converting governance-approved recommendations
into EVOSIA Mission artifacts. Supports DRAFT → APPROVED/REJECTED state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Approved states that allow planner integration
_APPROVED_STATES = frozenset({"APPROVED"})
_REJECTED_STATES = frozenset({"REJECTED"})
_VALID_STATES = frozenset({"DRAFT", "APPROVED", "REJECTED"})


@dataclass(frozen=True)
class TraceabilityLink:
    """Links a mission back through the full intelligence pipeline."""

    governance_finding_id: str
    engineering_finding_id: str
    recommendation_text: str
    repository_intelligence_source: str
    evidence_summary: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "governance_finding_id": self.governance_finding_id,
            "engineering_finding_id": self.engineering_finding_id,
            "recommendation_text": self.recommendation_text,
            "repository_intelligence_source": self.repository_intelligence_source,
            "evidence_summary": self.evidence_summary,
        }


@dataclass(frozen=True)
class GeneratedTask:
    """A single task within a generated mission."""

    task_id: str
    title: str
    command: list[str]
    dependencies: tuple[str, ...] = ()
    priority: int = 100
    required_capabilities: tuple[str, ...] = ()
    working_directory: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "title": self.title,
            "command": self.command,
            "dependencies": list(self.dependencies),
            "priority": self.priority,
            "required_capabilities": list(self.required_capabilities),
        }
        if self.working_directory is not None:
            d["working_directory"] = self.working_directory
        return d


@dataclass(frozen=True)
class DraftMission:
    """A generated mission, starting in DRAFT state.

    Supports DRAFT → APPROVED or DRAFT → REJECTED transitions.
    Only APPROVED missions may enter MissionPlanner.
    """

    mission_id: str
    title: str
    description: str
    objective: str
    tasks: tuple[GeneratedTask, ...]
    goals: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    working_directory: str | None = None
    repository: str | None = None
    state: str = "DRAFT"
    traceability: TraceabilityLink | None = None
    originating_finding_id: str = ""
    originating_recommendation: str = ""
    governance_approval_reference: str = ""
    estimated_effort: str = ""
    priority_score: float = 0.0
    mission_type: str = ""
    approved_at: str = ""
    approved_by: str = ""
    rejection_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": "1",
            "mission_id": self.mission_id,
            "title": self.title,
            "description": self.description,
            "goals": list(self.goals),
            "constraints": list(self.constraints),
            "tasks": [t.as_dict() for t in self.tasks],
            "required_capabilities": list(self.required_capabilities),
            "working_directory": self.working_directory,
            "repository": self.repository,
            "metadata": {
                "state": self.state,
                "objective": self.objective,
                "originating_finding_id": self.originating_finding_id,
                "originating_recommendation": self.originating_recommendation,
                "governance_approval_reference": self.governance_approval_reference,
                "estimated_effort": self.estimated_effort,
                "priority_score": round(self.priority_score, 2),
                "mission_type": self.mission_type,
                "approved_at": self.approved_at,
                "approved_by": self.approved_by,
                "rejection_reason": self.rejection_reason,
                **self.metadata,
            },
        }
        if self.traceability is not None:
            d["metadata"]["traceability"] = self.traceability.as_dict()
        return d

    @property
    def is_approved(self) -> bool:
        return self.state in _APPROVED_STATES

    @property
    def is_rejected(self) -> bool:
        return self.state in _REJECTED_STATES

    @property
    def is_draft(self) -> bool:
        return self.state == "DRAFT"

    def approve(self, by: str = "human", reason: str = "") -> DraftMission:
        """Return a new DraftMission with state=APPROVED."""
        if self.state != "DRAFT":
            raise ValueError(f"Cannot approve mission in state {self.state}; must be DRAFT")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return DraftMission(
            mission_id=self.mission_id, title=self.title, description=self.description,
            objective=self.objective, tasks=self.tasks, goals=self.goals,
            constraints=self.constraints, required_capabilities=self.required_capabilities,
            working_directory=self.working_directory, repository=self.repository,
            state="APPROVED", traceability=self.traceability,
            originating_finding_id=self.originating_finding_id,
            originating_recommendation=self.originating_recommendation,
            governance_approval_reference=self.governance_approval_reference,
            estimated_effort=self.estimated_effort, priority_score=self.priority_score,
            mission_type=self.mission_type, approved_at=now, approved_by=by,
            rejection_reason="", metadata=dict(self.metadata),
        )

    def reject(self, reason: str = "rejected by operator", by: str = "human") -> DraftMission:
        """Return a new DraftMission with state=REJECTED."""
        if self.state != "DRAFT":
            raise ValueError(f"Cannot reject mission in state {self.state}; must be DRAFT")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return DraftMission(
            mission_id=self.mission_id, title=self.title, description=self.description,
            objective=self.objective, tasks=self.tasks, goals=self.goals,
            constraints=self.constraints, required_capabilities=self.required_capabilities,
            working_directory=self.working_directory, repository=self.repository,
            state="REJECTED", traceability=self.traceability,
            originating_finding_id=self.originating_finding_id,
            originating_recommendation=self.originating_recommendation,
            governance_approval_reference=self.governance_approval_reference,
            estimated_effort=self.estimated_effort, priority_score=self.priority_score,
            mission_type=self.mission_type, approved_at="", approved_by="",
            rejection_reason=reason, metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class MissionRecommendationSummary:
    """Executive summary of generated mission recommendations."""

    total_governance_approvals: int
    missions_generated: int
    missions_by_type: dict[str, int]
    total_tasks: int
    traceability_validated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_governance_approvals": self.total_governance_approvals,
            "missions_generated": self.missions_generated,
            "missions_by_type": dict(self.missions_by_type),
            "total_tasks": self.total_tasks,
            "traceability_validated": self.traceability_validated,
        }


class MissionRecommendations:
    """Top-level mission recommendations model."""

    def __init__(
        self,
        *,
        repository: dict[str, Any] | None = None,
        draft_missions: tuple[DraftMission, ...] = (),
        summary: MissionRecommendationSummary | None = None,
        schema_version: str = "1",
    ) -> None:
        self.schema_version = schema_version
        self.repository = repository or {}
        self.draft_missions = draft_missions
        self.summary = summary or MissionRecommendationSummary(
            total_governance_approvals=0, missions_generated=0,
            missions_by_type={}, total_tasks=0, traceability_validated=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "draft_missions": [m.as_dict() for m in self.draft_missions],
            "summary": self.summary.as_dict(),
        }
