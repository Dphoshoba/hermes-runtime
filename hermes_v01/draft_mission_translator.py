"""Draft Mission → Mission translation.

Translates APPROVED DraftMission artifacts into the existing Mission model
consumed by MissionPlanner. Only APPROVED missions may be translated.
"""

from __future__ import annotations

from typing import Any

from .mission import Mission, MissionTask, RetryPolicy
from .mission_recommendation_models import DraftMission

# Traceability keys preserved through planning
_TRACEABILITY_KEYS = (
    "traceability",
    "originating_finding_id",
    "originating_recommendation",
    "governance_approval_reference",
    "approved_at",
    "approved_by",
    "mission_type",
    "estimated_effort",
    "priority_score",
)


def is_approved_draft(draft: DraftMission) -> bool:
    return draft.is_approved


def validate_draft_for_planning(draft: DraftMission) -> list[str]:
    """Validate a DraftMission is eligible for planner integration."""
    errors: list[str] = []
    if not draft.is_approved:
        errors.append(f"Mission {draft.mission_id} is not APPROVED (state={draft.state})")
    if not draft.traceability:
        errors.append(f"Mission {draft.mission_id} is missing governance traceability")
    if not draft.governance_approval_reference:
        errors.append(f"Mission {draft.mission_id} is missing governance approval reference")
    if not draft.tasks:
        errors.append(f"Mission {draft.mission_id} has no tasks")
    return errors


def _convert_task(gt: Any) -> MissionTask:
    """Convert a GeneratedTask to MissionTask."""
    return MissionTask(
        task_id=gt.task_id,
        title=gt.title,
        command=gt.command,
        dependencies=gt.dependencies,
        priority=gt.priority,
        retry_policy=None,
        required_capabilities=gt.required_capabilities,
        working_directory=gt.working_directory,
    )


def _build_traceability_metadata(draft: DraftMission) -> dict[str, Any]:
    """Preserve traceability through planning."""
    meta: dict[str, Any] = {}
    if draft.traceability:
        meta["traceability"] = draft.traceability.as_dict()
    meta["originating_finding_id"] = draft.originating_finding_id
    meta["originating_recommendation"] = draft.originating_recommendation
    meta["governance_approval_reference"] = draft.governance_approval_reference
    meta["approved_at"] = draft.approved_at
    meta["approved_by"] = draft.approved_by
    meta["mission_type"] = draft.mission_type
    meta["estimated_effort"] = draft.estimated_effort
    meta["priority_score"] = draft.priority_score
    meta["recommendation_generated"] = True
    meta["recommendation_schema_version"] = "1"
    return meta


def translate_draft_to_mission(draft: DraftMission) -> Mission:
    """Translate an APPROVED DraftMission into a Mission.

    Raises ValueError if draft is not APPROVED or is missing traceability.
    """
    errors = validate_draft_for_planning(draft)
    if errors:
        raise ValueError(f"Cannot translate draft: {'; '.join(errors)}")

    tasks = tuple(_convert_task(t) for t in draft.tasks)
    metadata = _build_traceability_metadata(draft)

    return Mission(
        mission_id=draft.mission_id,
        title=f"[APPROVED] {draft.title}",
        description=draft.description,
        tasks=tasks,
        goals=draft.goals,
        constraints=draft.constraints,
        required_capabilities=draft.required_capabilities,
        working_directory=draft.working_directory,
        repository=draft.repository,
        metadata=metadata,
    )
