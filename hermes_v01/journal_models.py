"""Engineering Journal — append-only event log for pipeline observability.

Every pipeline stage emits a JournalEvent. Events are immutable, ordered,
and content-addressed. The journal provides a complete audit trail of all
engineering activity without modifying existing pipeline behavior.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{dt.microsecond:06d}Z"


def _event_id(timestamp: str, event_type: str, payload_sha256: str) -> str:
    raw = f"{timestamp}|{event_type}|{payload_sha256}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _canonical_payload_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EVENT_TYPES = (
    "readiness.assessed",
    "readiness.blocked",
    "repo.scanned",
    "repo.analyzed",
    "engineering.analyzed",
    "governance.decided",
    "recommendation.generated",
    "recommendation.approved",
    "recommendation.rejected",
    "mission.created",
    "mission.planned",
    "mission.started",
    "mission.completed",
    "mission.failed",
    "mission.cancelled",
    "mission.aborted",
    "mission.paused",
    "mission.resumed",
    "evidence.recorded",
    "review.completed",
    "health.checked",
    "github.metadata_fetched",
    "github.branches_listed",
    "github.pr_listed",
    "github.actions_checked",
    "github.materialized",
)

# Stage categories for summary grouping
STAGE_CATEGORIES: dict[str, str] = {
    "readiness.assessed": "readiness",
    "readiness.blocked": "readiness",
    "repo.scanned": "repository_intelligence",
    "repo.analyzed": "repository_intelligence",
    "engineering.analyzed": "engineering_intelligence",
    "governance.decided": "governance",
    "recommendation.generated": "mission_recommendation",
    "recommendation.approved": "mission_recommendation",
    "recommendation.rejected": "mission_recommendation",
    "mission.created": "mission_planning",
    "mission.planned": "mission_planning",
    "mission.started": "mission_execution",
    "mission.completed": "mission_execution",
    "mission.failed": "mission_execution",
    "mission.cancelled": "mission_execution",
    "mission.aborted": "mission_execution",
    "mission.paused": "mission_execution",
    "mission.resumed": "mission_execution",
    "evidence.recorded": "evidence",
    "review.completed": "review",
    "health.checked": "health",
    "github.metadata_fetched": "github",
    "github.branches_listed": "github",
    "github.pr_listed": "github",
    "github.actions_checked": "github",
    "github.materialized": "github",
}


# ---------------------------------------------------------------------------
# Canonical data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JournalEvent:
    """A single immutable event in the engineering journal."""

    event_id: str
    timestamp: str
    event_type: str
    stage: str
    repository: str | None
    actor: str
    payload: dict[str, Any]
    payload_sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "stage": self.stage,
            "actor": self.actor,
            "payload": self.payload,
            "payload_sha256": self.payload_sha256,
        }
        if self.repository is not None:
            data["repository"] = self.repository
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JournalEvent:
        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            event_type=data["event_type"],
            stage=data["stage"],
            repository=data.get("repository"),
            actor=data["actor"],
            payload=data["payload"],
            payload_sha256=data["payload_sha256"],
            metadata=data.get("metadata", {}),
        )

    def verify_integrity(self) -> bool:
        """Verify the event's content hash matches its payload."""
        return _canonical_payload_sha256(self.payload) == self.payload_sha256


def create_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    repository: str | None = None,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> JournalEvent:
    """Create a new JournalEvent with deterministic ID generation."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type!r}. Valid types: {EVENT_TYPES}")

    ts = _format_utc(clock() if clock else _utc_now())
    payload_hash = _canonical_payload_sha256(payload)
    eid = _event_id(ts, event_type, payload_hash)
    stage = STAGE_CATEGORIES.get(event_type, "unknown")

    return JournalEvent(
        event_id=eid,
        timestamp=ts,
        event_type=event_type,
        stage=stage,
        repository=repository,
        actor=actor,
        payload=payload,
        payload_sha256=payload_hash,
        metadata=metadata or {},
    )
