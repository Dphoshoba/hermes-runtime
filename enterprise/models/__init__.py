"""SQLAlchemy ORM models for the Engineering Command Center."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, JSON, ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User & Authentication
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# Repository Registry
# ---------------------------------------------------------------------------

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    default_branch = Column(String(255), default="main")
    language = Column(String(100))
    status = Column(String(50), default="active")
    provider = Column(String(50), default="local")
    identifier = Column(String(512))
    commit_sha = Column(String(40))
    visibility = Column(String(50))
    last_scanned_at = Column(DateTime)
    last_synced_at = Column(DateTime)
    health_score = Column(Float)
    findings_count = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    journal_events = relationship("JournalEvent", back_populates="repository_rel")
    findings = relationship("Finding", back_populates="repository_rel")
    missions = relationship("Mission", back_populates="repository_rel")
    reports = relationship("Report", back_populates="repository_rel")
    scan_jobs = relationship("ScanJob", back_populates="repository_rel")


# ---------------------------------------------------------------------------
# Engineering Journal
# ---------------------------------------------------------------------------

class JournalEvent(Base):
    __tablename__ = "journal_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    timestamp = Column(String(30), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    stage = Column(String(100), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    actor = Column(String(255), default="system")
    payload = Column(JSON, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    repository_rel = relationship("Repository", back_populates="journal_events")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    finding_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    module = Column(String(512))
    priority_score = Column(Float)
    effort = Column(String(50))
    status = Column(String(50), default="open", index=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Evidence & Risk Gate routing (machine authority) — Post Cycle 8.
    # Additive; legacy rows remain untouched (these are nullable).
    gate_state = Column(String(50), nullable=True)
    risk_band = Column(String(20), nullable=True)
    review_rank = Column(Float, nullable=True)
    legacy_decision = Column(String(50), nullable=True)

    repository_rel = relationship("Repository", back_populates="findings")


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------

class Mission(Base):
    __tablename__ = "missions"
    __table_args__ = (UniqueConstraint("mission_id", "repository_id", name="uq_mission_per_repo"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(255), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    mission_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending", index=True)
    priority = Column(Integer, default=0)
    configuration = Column(JSON, default=dict)
    created_by = Column(String(255))
    approved_by = Column(String(255))
    approved_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    repository_rel = relationship("Repository", back_populates="missions")
    report = relationship("Report", back_populates="mission_rel", uselist=False)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(36), ForeignKey("missions.id"), index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    title = Column(String(512), nullable=False)
    status = Column(String(50), nullable=False)
    summary = Column(Text)
    report_data = Column(JSON, nullable=False)
    duration_seconds = Column(Float)
    tasks_planned = Column(Integer)
    tasks_completed = Column(Integer)
    tasks_failed = Column(Integer)
    created_at = Column(DateTime, default=_utcnow)

    mission_rel = relationship("Mission", back_populates="report")
    repository_rel = relationship("Repository", back_populates="reports")


# ---------------------------------------------------------------------------
# Scan Jobs
# ---------------------------------------------------------------------------

class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    scan_type = Column(String(50), default="full")
    branch = Column(String(255))
    commit_sha = Column(String(40))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    error_message = Column(Text)
    stages_completed = Column(JSON, default=list)
    current_stage = Column(String(100))
    findings_count = Column(Integer, default=0)
    attempt = Column(Integer, default=1)
    previous_scan_id = Column(String(36), ForeignKey("scan_jobs.id"))
    requested_by = Column(String(255))
    cancellation_requested_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    failure_classification = Column(String(100))
    stage_timings = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    repository_rel = relationship("Repository", back_populates="scan_jobs")
    history = relationship("ScanHistory", back_populates="scan_job_rel", order_by="ScanHistory.created_at")
    retry_chain = relationship("ScanJob", remote_side=[id])


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(String(36), primary_key=True, default=_uuid)
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id"), nullable=False, index=True)
    stage = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text)
    duration_seconds = Column(Float)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    scan_job_rel = relationship("ScanJob", back_populates="history")


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Trial Model
# ---------------------------------------------------------------------------

class OperationalTrial(Base):
    __tablename__ = "operational_trials"

    id = Column(String(36), primary_key=True, default=_uuid)
    trial_id = Column(String(100), unique=True, nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    status = Column(String(50), default="PLANNED", index=True)
    operator = Column(String(255), nullable=False)
    repositories = Column(JSON, default=list)
    baseline_version = Column(String(100))
    baseline_commit = Column(String(40))
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Daily Snapshot
# ---------------------------------------------------------------------------

class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    trial_id = Column(String(100), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)
    hermes_version = Column(String(100))
    hermes_commit = Column(String(40))
    repositories = Column(JSON, default=list)
    metrics = Column(JSON, default=dict)
    operator_feedback = Column(JSON, default=list)
    friction = Column(JSON, default=list)
    failures = Column(JSON, default=list)
    safety_incidents = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Operator Feedback
# ---------------------------------------------------------------------------

class OperatorFeedback(Base):
    __tablename__ = "operator_feedback"

    id = Column(String(36), primary_key=True, default=_uuid)
    trial_id = Column(String(100), nullable=False, index=True)
    finding_id = Column(String(36), ForeignKey("findings.id"), index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    classification = Column(String(50), nullable=False)
    notes = Column(Text)
    operator = Column(String(255))
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Friction Journal
# ---------------------------------------------------------------------------

class FrictionRecord(Base):
    __tablename__ = "friction_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    trial_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=_utcnow)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    category = Column(String(100), nullable=False)
    severity = Column(String(50), default="medium")
    description = Column(Text, nullable=False)
    workaround = Column(Text)
    related_scan_id = Column(String(36), ForeignKey("scan_jobs.id"))
    related_finding_id = Column(String(36), ForeignKey("findings.id"))
    related_mission_id = Column(String(36), ForeignKey("missions.id"))
    status = Column(String(50), default="open")
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Feature Proposal
# ---------------------------------------------------------------------------

class FeatureProposal(Base):
    __tablename__ = "feature_proposals"

    id = Column(String(36), primary_key=True, default=_uuid)
    trial_id = Column(String(100), nullable=False, index=True)
    problem = Column(Text, nullable=False)
    observed_evidence = Column(Text, nullable=False)
    frequency = Column(String(50))
    affected_repositories = Column(JSON, default=list)
    current_workaround = Column(Text)
    risk = Column(Text)
    expected_benefit = Column(Text)
    success_metric = Column(Text)
    implementation_estimate = Column(String(50))
    decision = Column(String(50), default="NEEDS_MORE_EVIDENCE")
    decision_notes = Column(Text)
    decided_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# Finding Adjudication — Evidence-Based Human Review
# ---------------------------------------------------------------------------

class FindingAdjudication(Base):
    __tablename__ = "finding_adjudications"
    __table_args__ = (
        UniqueConstraint("finding_id", "operator", "reviewed_at", name="uq_adjudication_per_operator_time"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    finding_id = Column(String(36), ForeignKey("findings.id"), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    scan_id = Column(String(36), ForeignKey("scan_jobs.id"))
    trial_id = Column(String(100), index=True)

    classification = Column(String(50), nullable=False, index=True)
    observation_status = Column(String(30), default="SUPPORTED")
    concern_status = Column(String(30), default="POSSIBLE")
    actionability_status = Column(String(30), default="NEEDS_MORE_EVIDENCE")
    file_context = Column(String(30), default="UNKNOWN")
    exceedance_ratio = Column(Float)

    operator = Column(String(255), nullable=False)
    operator_notes = Column(Text)
    reviewed_at = Column(DateTime, nullable=False, default=_utcnow)
    source = Column(String(50), default="human_review")
    confidence = Column(Float, default=1.0)
    evidence_snapshot = Column(JSON, default=dict)
    governance_decision_at_review = Column(String(50))
    related_mission_ids = Column(JSON, default=list)
    schema_version = Column(String(20), default="1.0")

    # Deterministic policy suppression (Post Cycle 8) — kept distinct from human
    # NOT_ACTIONABLE. Auditable and recoverable for review.
    policy_suppressed = Column(Boolean, default=False, index=True)
    suppression_rule_id = Column(String(100), nullable=True, index=True)
    suppression_rule_version = Column(String(50), nullable=True)

    finding = relationship("Finding")
    repository = relationship("Repository")


# ---------------------------------------------------------------------------
# Mission ↔ Finding Explicit Linkage
# ---------------------------------------------------------------------------

class MissionFindingLink(Base):
    __tablename__ = "mission_finding_links"
    __table_args__ = (
        UniqueConstraint("mission_id", "finding_id", name="uq_mission_finding_link"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(255), nullable=False, index=True)
    finding_id = Column(String(36), ForeignKey("findings.id"), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    relationship_type = Column(String(30), default="PRIMARY")
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# Project Context Engine (Guided Mode)
# ---------------------------------------------------------------------------

class ProjectContext(Base):
    __tablename__ = "project_context"
    __table_args__ = (
        UniqueConstraint("repository_id", "topic", "key", name="uq_context_item"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)
    project_id = Column(String(100), index=True)

    topic = Column(String(100), nullable=False, index=True)
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)

    source = Column(String(50), default="human_confirmed")
    actor = Column(String(255), nullable=False)
    scope = Column(String(100), default="project")
    confidence = Column(String(30), default="human_confirmed")

    superseded_by = Column(String(36), ForeignKey("project_context.id"), nullable=True)
    is_current = Column(Boolean, default=True, index=True)

    provenance = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# Workspace / Tenant Isolation (Hosted Beta — M2)
# ---------------------------------------------------------------------------

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class UserWorkspace(Base):
    __tablename__ = "user_workspaces"
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_user_workspace"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    role = Column(String(30), default="member")  # admin, member
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User")
    workspace = relationship("Workspace")


# ---------------------------------------------------------------------------
# Prepared Change Sandbox (Guided Mode — M6)
# ---------------------------------------------------------------------------

class PreparedChange(Base):
    __tablename__ = "prepared_changes"

    id = Column(String(36), primary_key=True, default=_uuid)
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    repository_id = Column(String(36), ForeignKey("repositories.id"), index=True)

    title = Column(String(512), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="preparing", index=True)

    workspace_path = Column(String(1024))
    affected_files = Column(JSON, default=list)
    diff_content = Column(Text)
    rollback_representation = Column(Text)

    validation_status = Column(String(50), default="pending")
    validation_output = Column(Text)

    source_commit_sha = Column(String(40))
    provenance = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)

    created_by = Column(String(255))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# Local Agent — Device Trust Domain (LA1)
# ---------------------------------------------------------------------------

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(128), unique=True, nullable=False, index=True)
    device_name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)  # "macos", "windows", "linux"
    agent_version = Column(String(50), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Status
    status = Column(String(30), default="pending", nullable=False)  # pending, active, revoked

    # Capabilities (JSON array of capability strings)
    capabilities = Column(JSON, default=list)

    # Timestamps
    registered_at = Column(DateTime, default=_utcnow)
    last_seen_at = Column(DateTime)
    revoked_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    user = relationship("User")


class BootstrapToken(Base):
    """Server-side record of issued bootstrap tokens (hashed).

    The plaintext token is returned once at creation and never persisted.
    This table enforces single-use consumption and tracks expiry.
    """
    __tablename__ = "bootstrap_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    device_id = Column(String(128), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    consumed = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# Local Agent — Project Authorization (LA3)
# ---------------------------------------------------------------------------

class DeviceProject(Base):
    """Device-project relationship for authorized projects.

    Maps a device to an explicitly authorized project root.
    No raw local paths stored in cloud DB.
    """
    __tablename__ = "device_projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(128), ForeignKey("devices.device_id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    local_root_fingerprint = Column(String(128))  # SHA-256 of canonical path

    # Status
    status = Column(String(30), default="active", nullable=False)  # active, revoked
    authority = Column(String(50), default="REVIEW_ONLY", nullable=False)

    # Timestamps
    registered_at = Column(DateTime, default=_utcnow)
    revoked_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    device = relationship("Device")
    user = relationship("User")


class PairingRequest(Base):
    """Server-side record of browser-assisted pairing requests.

    High-entropy opaque identifier, short-lived, single-use.
    Created by Connector, approved by authenticated user in browser.
    Consumed to issue device credential.
    """
    __tablename__ = "pairing_requests"

    id = Column(String(36), primary_key=True, default=_uuid)
    pairing_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    device_name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    agent_version = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    # PENDING, APPROVED, CONSUMED, EXPIRED, DENIED
    approved_at = Column(DateTime, nullable=True)
    consumed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class ProjectAuthorizationToken(Base):
    """Server-side record of issued project authorization tokens (hashed).

    Short-lived, single-use tokens for authorizing project registration.
    Created by authenticated user, consumed by agent during registration.
    """
    __tablename__ = "project_authorization_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    device_id = Column(String(128), ForeignKey("devices.device_id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    consumed = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# Local Agent — Governed Scan Jobs (LA4)
# ---------------------------------------------------------------------------

class AgentJob(Base):
    """Governed scan job for Local Agent execution.

    Created by authenticated user via control plane.
    Executed by device via agent work plane.
    Device may NEVER create these — only fetch and perform predefined work.
    """
    __tablename__ = "agent_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String(128), ForeignKey("devices.device_id"), nullable=False, index=True)
    device_project_id = Column(String(36), ForeignKey("device_projects.id"), nullable=False, index=True)

    # Governed operation — only PROJECT_SCAN for LA4
    operation_type = Column(String(50), nullable=False, default="PROJECT_SCAN")

    # Lifecycle status
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    # PENDING → STARTED → COMPLETED | FAILED | EXPIRED

    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    truncated = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User")
    device = relationship("Device")
    device_project = relationship("DeviceProject")
