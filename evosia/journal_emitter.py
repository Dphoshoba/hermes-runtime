"""Journal Instrumentation — emit events from all pipeline stages.

Provides a thin JournalEmitter that wraps a JournalStore and offers
stage-specific emit helpers. Each helper extracts relevant data from
pipeline outputs and creates a JournalEvent without modifying the
existing pipeline behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .journal_models import JournalEvent, create_event
from .journal_store import JournalStore


class JournalEmitter:
    """High-level emitter with helpers for every pipeline stage."""

    def __init__(
        self,
        store: JournalStore,
        *,
        actor: str = "system",
        clock: Callable | None = None,
    ) -> None:
        self._store = store
        self._actor = actor
        self._clock = clock

    @property
    def store(self) -> JournalStore:
        return self._store

    def _emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        repository: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JournalEvent:
        event = create_event(
            event_type,
            payload,
            repository=repository,
            actor=self._actor,
            metadata=metadata,
            clock=self._clock,
        )
        self._store.append(event)
        return event

    # -----------------------------------------------------------------------
    # Readiness
    # -----------------------------------------------------------------------

    def emit_readiness_assessed(
        self,
        readiness: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("readiness.assessed", readiness, repository=repository)

    def emit_readiness_blocked(
        self,
        readiness: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("readiness.blocked", readiness, repository=repository)

    # -----------------------------------------------------------------------
    # Repository Intelligence
    # -----------------------------------------------------------------------

    def emit_repo_scanned(
        self,
        scan_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("repo.scanned", scan_summary, repository=repository)

    def emit_repo_analyzed(
        self,
        analysis_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("repo.analyzed", analysis_summary, repository=repository)

    # -----------------------------------------------------------------------
    # Engineering Intelligence
    # -----------------------------------------------------------------------

    def emit_engineering_analyzed(
        self,
        engineering_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "engineering.analyzed", engineering_summary, repository=repository
        )

    # -----------------------------------------------------------------------
    # Governance
    # -----------------------------------------------------------------------

    def emit_governance_decided(
        self,
        governance_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "governance.decided", governance_summary, repository=repository
        )

    # -----------------------------------------------------------------------
    # Evidence & Risk Gate (Post Cycle 8)
    # -----------------------------------------------------------------------

    def emit_gate_evaluated(
        self,
        gate_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("gate.evaluated", gate_summary, repository=repository)

    def emit_gate_routed(
        self,
        gate: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("gate.routed", gate, repository=repository)

    def emit_policy_suppression(
        self,
        suppression: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "policy.suppression", suppression, repository=repository
        )

    def emit_human_adjudication(
        self,
        adjudication: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "human.adjudication", adjudication, repository=repository
        )

    def emit_mission_eligibility(
        self,
        eligibility: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "mission.eligibility", eligibility, repository=repository
        )

    # -----------------------------------------------------------------------
    # Mission Recommendation
    # -----------------------------------------------------------------------

    def emit_recommendation_generated(
        self,
        recommendation_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "recommendation.generated", recommendation_summary, repository=repository
        )

    def emit_recommendation_approved(
        self,
        approval_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "recommendation.approved", approval_summary, repository=repository
        )

    def emit_recommendation_rejected(
        self,
        rejection_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "recommendation.rejected", rejection_summary, repository=repository
        )

    # -----------------------------------------------------------------------
    # Mission Planning
    # -----------------------------------------------------------------------

    def emit_mission_created(
        self,
        mission_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.created", mission_summary, repository=repository)

    def emit_mission_planned(
        self,
        plan_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.planned", plan_summary, repository=repository)

    # -----------------------------------------------------------------------
    # Mission Execution
    # -----------------------------------------------------------------------

    def emit_mission_started(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.started", execution_summary, repository=repository)

    def emit_mission_completed(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "mission.completed", execution_summary, repository=repository
        )

    def emit_mission_failed(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.failed", execution_summary, repository=repository)

    def emit_mission_cancelled(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "mission.cancelled", execution_summary, repository=repository
        )

    def emit_mission_aborted(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.aborted", execution_summary, repository=repository)

    def emit_mission_paused(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.paused", execution_summary, repository=repository)

    def emit_mission_resumed(
        self,
        execution_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("mission.resumed", execution_summary, repository=repository)

    # -----------------------------------------------------------------------
    # Evidence
    # -----------------------------------------------------------------------

    def emit_evidence_recorded(
        self,
        evidence_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "evidence.recorded", evidence_summary, repository=repository
        )

    # -----------------------------------------------------------------------
    # Review
    # -----------------------------------------------------------------------

    def emit_review_completed(
        self,
        review_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("review.completed", review_summary, repository=repository)

    # -----------------------------------------------------------------------
    # Health
    # -----------------------------------------------------------------------

    def emit_health_checked(
        self,
        health_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("health.checked", health_summary, repository=repository)

    # -----------------------------------------------------------------------
    # GitHub Provider
    # -----------------------------------------------------------------------

    def emit_github_metadata_fetched(
        self,
        github_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "github.metadata_fetched", github_summary, repository=repository
        )

    def emit_github_branches_listed(
        self,
        github_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "github.branches_listed", github_summary, repository=repository
        )

    def emit_github_pr_listed(
        self,
        github_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit("github.pr_listed", github_summary, repository=repository)

    def emit_github_actions_checked(
        self,
        github_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "github.actions_checked", github_summary, repository=repository
        )

    def emit_github_materialized(
        self,
        github_summary: dict[str, Any],
        *,
        repository: str | None = None,
    ) -> JournalEvent:
        return self._emit(
            "github.materialized", github_summary, repository=repository
        )
