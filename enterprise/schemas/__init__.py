"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_serializer


def _ensure_utc_z(value: datetime | None) -> str | None:
    """Serialize a datetime as ISO 8601 with explicit 'Z' suffix.

    SQLite Column(DateTime) strips timezone info, so SQLAlchemy returns
    naive datetimes that are actually UTC. This serializer ensures the
    API always emits timezone-aware ISO strings so browsers parse them
    correctly as UTC rather than local time.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=1024)
    default_branch: str = "main"
    language: str | None = None
    provider: str = "local"
    identifier: str | None = None


class RepositoryUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    default_branch: str | None = None
    language: str | None = None
    status: str | None = None
    identifier: str | None = None


class RepositoryResponse(BaseModel):
    id: str
    name: str
    url: str
    default_branch: str
    language: str | None
    status: str
    provider: str
    identifier: str | None
    commit_sha: str | None
    visibility: str | None
    last_scanned_at: datetime | None
    last_synced_at: datetime | None
    health_score: float | None
    findings_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

class JournalEventResponse(BaseModel):
    id: str
    event_id: str
    timestamp: str
    event_type: str
    stage: str
    repository_id: str | None
    actor: str
    payload: dict[str, Any]
    payload_sha256: str
    metadata_json: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True


class JournalQuery(BaseModel):
    event_type: str | None = None
    stage: str | None = None
    repository_id: str | None = None
    actor: str | None = None
    after: str | None = None
    before: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class FindingResponse(BaseModel):
    id: str
    repository_id: str | None
    finding_type: str
    severity: str
    category: str
    title: str
    description: str | None
    module: str | None
    priority_score: float | None
    effort: str | None
    status: str
    created_at: datetime
    # Evidence & Risk Gate authority fields (Post Cycle 8) — client distinction.
    # These are SEPARATE sources of authority and must never be overloaded.
    gate_state: str | None = None            # machine routing: REQUIRES_REVIEW / etc.
    risk_band: str | None = None
    review_rank: float | None = None
    legacy_decision: str | None = None       # historical APPROVED (advisory only)
    policy_suppressed: bool | None = None    # deterministic suppression (machine, not human)
    suppression_rule_id: str | None = None
    suppression_rule_version: str | None = None
    human_classification: str | None = None  # current effective human adjudication
    human_operator: str | None = None
    mission_eligible: bool = False           # True ONLY with human ACTIONABLE

    class Config:
        from_attributes = True


class FindingQuery(BaseModel):
    repository_id: str | None = None
    severity: str | None = None
    category: str | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------

class MissionResponse(BaseModel):
    id: str
    mission_id: str
    repository_id: str | None
    title: str
    description: str | None
    mission_type: str
    status: str
    priority: int
    created_by: str | None
    approved_by: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class MissionQuery(BaseModel):
    repository_id: str | None = None
    status: str | None = None
    mission_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportResponse(BaseModel):
    id: str
    mission_id: str | None
    repository_id: str | None
    title: str
    status: str
    summary: str | None
    report_data: dict[str, Any]
    duration_seconds: float | None
    tasks_planned: int | None
    tasks_completed: int | None
    tasks_failed: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportQuery(BaseModel):
    repository_id: str | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_repositories: int
    active_repositories: int
    total_findings: int
    open_findings: int
    critical_findings: int
    high_findings: int
    total_missions: int
    pending_missions: int
    running_missions: int
    completed_missions: int
    failed_missions: int
    total_reports: int
    avg_health_score: float | None
    journal_events_today: int


class DashboardActivity(BaseModel):
    events: list[JournalEventResponse]
    total: int


# ---------------------------------------------------------------------------
# Scan Jobs
# ---------------------------------------------------------------------------

class ScanJobCreate(BaseModel):
    repository_id: str
    scan_type: str = "full"
    branch: str | None = None


class ScanJobResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    scan_type: str
    branch: str | None
    commit_sha: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    error_message: str | None
    stages_completed: list[str]
    current_stage: str | None
    findings_count: int
    attempt: int
    previous_scan_id: str | None
    requested_by: str | None
    cancellation_requested_at: datetime | None
    cancelled_at: datetime | None
    failure_classification: str | None
    stage_timings: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ScanJobQuery(BaseModel):
    repository_id: str | None = None
    status: str | None = None
    scan_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ScanHistoryResponse(BaseModel):
    id: str
    scan_job_id: str
    stage: str
    status: str
    message: str | None
    duration_seconds: float | None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dashboard Activity
# ---------------------------------------------------------------------------

class DashboardActivityResponse(BaseModel):
    repositories_total: int
    repositories_ready: int
    repositories_blocked: int
    scans_queued: int
    scans_running: int
    scans_completed_since: int
    scans_failed_since: int
    new_findings_since: int
    governance_approved_since: int
    governance_rejected_since: int
    draft_missions_since: int
    ci_failures_since: int
    latest_activity: list[JournalEventResponse]
    average_repository_health: float | None


# ---------------------------------------------------------------------------
# Overnight Summary
# ---------------------------------------------------------------------------

class OvernightSummaryResponse(BaseModel):
    window_start: str
    window_end: str
    repositories_scanned: int
    blocked_repositories: int
    successful_scans: int
    failed_scans: int
    new_findings: int
    resolved_findings: int
    governance_decisions: int
    draft_missions: int
    ci_failures: int
    top_repositories_requiring_attention: list[dict[str, Any]]
    summary: str


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Trial
# ---------------------------------------------------------------------------

class TrialCreate(BaseModel):
    trial_id: str = Field(min_length=1, max_length=100)
    operator: str = Field(min_length=1, max_length=255)
    repositories: list[str] = Field(default_factory=list)
    baseline_version: str | None = None
    baseline_commit: str | None = None


class TrialResponse(BaseModel):
    id: str
    trial_id: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    operator: str
    repositories: list[str]
    baseline_version: str | None
    baseline_commit: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Daily Snapshot
# ---------------------------------------------------------------------------

class DailySnapshotResponse(BaseModel):
    id: str
    trial_id: str
    date: str
    hermes_version: str | None
    hermes_commit: str | None
    repositories: list[str]
    metrics: dict[str, Any]
    operator_feedback: list[dict[str, Any]]
    friction: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    safety_incidents: list[dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Operator Feedback
# ---------------------------------------------------------------------------

class FeedbackCreate(BaseModel):
    finding_id: str
    repository_id: str | None = None
    classification: str = Field(pattern=r"^(USEFUL|FALSE_POSITIVE|NOT_ACTIONABLE|NEEDS_MORE_EVIDENCE|DUPLICATE|UNKNOWN)$")
    notes: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    trial_id: str
    finding_id: str
    repository_id: str | None
    classification: str
    notes: str | None
    operator: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Friction Journal
# ---------------------------------------------------------------------------

class FrictionCreate(BaseModel):
    repository_id: str | None = None
    category: str = Field(min_length=1, max_length=100)
    severity: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    description: str = Field(min_length=1)
    workaround: str | None = None
    related_scan_id: str | None = None
    related_finding_id: str | None = None
    related_mission_id: str | None = None


class FrictionResponse(BaseModel):
    id: str
    trial_id: str
    timestamp: datetime
    repository_id: str | None
    category: str
    severity: str
    description: str
    workaround: str | None
    related_scan_id: str | None
    related_finding_id: str | None
    related_mission_id: str | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Feature Proposal
# ---------------------------------------------------------------------------

class FeatureProposalCreate(BaseModel):
    problem: str = Field(min_length=1)
    observed_evidence: str = Field(min_length=1)
    frequency: str | None = None
    affected_repositories: list[str] = Field(default_factory=list)
    current_workaround: str | None = None
    risk: str | None = None
    expected_benefit: str | None = None
    success_metric: str | None = None
    implementation_estimate: str | None = None


class FeatureProposalResponse(BaseModel):
    id: str
    trial_id: str
    problem: str
    observed_evidence: str
    frequency: str | None
    affected_repositories: list[str]
    current_workaround: str | None
    risk: str | None
    expected_benefit: str | None
    success_metric: str | None
    implementation_estimate: str | None
    decision: str
    decision_notes: str | None
    decided_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class FeatureDecision(BaseModel):
    decision: str = Field(pattern=r"^(ACCEPT|DEFER|REJECT|NEEDS_MORE_EVIDENCE)$")
    decision_notes: str | None = None


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Daily Metrics
# ---------------------------------------------------------------------------

class DailyMetrics(BaseModel):
    date: str
    repositories_registered: int
    repositories_scanned: int
    successful_scans: int
    failed_scans: int
    blocked_repositories: int
    cancelled_scans: int
    retried_scans: int
    findings_generated: int
    findings_new: int
    findings_resolved: int | None
    findings_by_severity: dict[str, int]
    findings_by_category: dict[str, int]
    governance_approved: int
    governance_rejected: int
    governance_needs_evidence: int
    governance_duplicate: int
    missions_generated: int
    missions_approved: int
    missions_rejected: int
    false_positives_confirmed: int
    useful_findings_confirmed: int
    unsafe_recommendations_detected: int
    evidence_quality_issues: int
    average_scan_duration: float | None
    p50_scan_duration: float | None
    p95_scan_duration: float | None
    slowest_pipeline_stage: str | None
    api_failures: int
    ui_failures: int
    journal_integrity_failures: int


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Trust Metrics
# ---------------------------------------------------------------------------

class TrustMetrics(BaseModel):
    finding_precision: float | None
    operator_acceptance_rate: float | None
    scan_reliability: float | None
    retry_recovery_rate: float | None
    safety_violation_count: int
    journal_integrity_failure_count: int
    confirmed_useful: int
    confirmed_false_positives: int
    total_reviewed: int
    approved_actionable: int
    reviewed_actionable: int
    successful_scans: int
    completed_scan_attempts: int
    successful_retries: int
    retry_attempts: int


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Morning Brief
# ---------------------------------------------------------------------------

class MorningBrief(BaseModel):
    greeting: str
    period_start: str
    period_end: str
    repositories_scanned: int
    successful_scans: int
    failed_scans: int
    blocked_repositories: int
    new_findings: int
    high_critical_findings: int
    useful_findings_confirmed: int
    false_positives_confirmed: int
    governance_approvals: int
    governance_rejections: int
    draft_missions: int
    retries: int
    recovered_failures: int
    average_scan_time: float | None
    repositories_requiring_attention: list[dict[str, Any]]
    operational_friction: int
    safety_incidents: int
    recommended_review_order: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Trial Dashboard
# ---------------------------------------------------------------------------

class TrialDaySummary(BaseModel):
    day_number: int
    date: str
    scans: int
    reliability: float | None
    findings: int
    useful: int
    false_positive: int
    governance: int
    missions: int
    failures: int
    friction: int


class TrialDashboard(BaseModel):
    trial_id: str
    status: str
    started_at: str
    days_completed: int
    daily_summaries: list[TrialDaySummary]
    cumulative: dict[str, Any]


# ---------------------------------------------------------------------------
# 7-Day Operational Validation — Scheduling
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    repository_id: str
    cron_expression: str = Field(min_length=5, max_length=100)
    enabled: bool = True


class ScheduleResponse(BaseModel):
    id: str
    repository_id: str
    cron_expression: str
    enabled: bool
    last_run: datetime | None
    next_run: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Human Review — Finding Adjudication
# ---------------------------------------------------------------------------

class AdjudicationCreate(BaseModel):
    classification: str = Field(
        pattern=r"^(USEFUL|FALSE_POSITIVE|NOT_ACTIONABLE|NEEDS_MORE_EVIDENCE|DUPLICATE|UNKNOWN)$"
    )
    notes: str | None = None
    operator: str = Field(min_length=1, max_length=255)
    trial_id: str | None = None


class AdjudicationResponse(BaseModel):
    id: str
    finding_id: str
    repository_id: str | None
    classification: str
    observation_status: str
    concern_status: str
    actionability_status: str
    file_context: str
    exceedance_ratio: float | None
    operator: str
    operator_notes: str | None
    reviewed_at: datetime
    source: str
    confidence: float
    governance_decision_at_review: str | None
    related_mission_ids: list[str]
    schema_version: str

    class Config:
        from_attributes = True


class ReviewQueueItem(BaseModel):
    finding_id: str
    db_id: str
    repository_id: str | None
    repository_name: str
    severity: str
    category: str
    title: str
    description: str
    module: str
    file_context: str
    line_count: int | None
    exceedance_ratio: float | None
    exceedance_tier: str | None
    evidence_references: list[dict[str, Any]]
    governance_decision: str
    governance_rationale: str
    observation_status: str
    concern_status: str
    actionability_status: str
    mission_linkage: Any
    current_adjudication: str | None
    operator: str | None
    operator_notes: str | None
    reviewed_at: str | None


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    limit: int
    offset: int
    pending_review: int | None = None


class ReviewSummaryResponse(BaseModel):
    total_reviewed: int
    useful: int
    false_positive: int
    not_actionable: int
    needs_more_evidence: int
    duplicate: int
    unknown: int
    finding_precision: float | None
    actionability_rate: float | None
    pending_review: int


# ---------------------------------------------------------------------------
# Local Agent — Device Trust Domain (LA1)
# ---------------------------------------------------------------------------

class DeviceRegister(BaseModel):
    """User-authorized request to register a new device."""
    device_name: str = Field(min_length=1, max_length=255)
    platform: str = Field(pattern=r"^(macos|windows|linux)$")
    agent_version: str = Field(min_length=1, max_length=50)
    capabilities: list[str] = Field(default_factory=list)


class DeviceRegisterResponse(BaseModel):
    """Response containing a single-use bootstrap token."""
    bootstrap_token: str
    expires_at: datetime
    device_id: str

    @field_serializer("expires_at")
    def _serialize_dt(self, value: datetime) -> str:
        return _ensure_utc_z(value)


class DeviceTokenExchange(BaseModel):
    """Agent request to exchange bootstrap token for device credential."""
    bootstrap_token: str


class DeviceTokenResponse(BaseModel):
    """Device credential issued after bootstrap exchange."""
    device_id: str
    access_token: str
    token_type: str = "device"
    expires_at: datetime


class DeviceResponse(BaseModel):
    """Device metadata returned by control plane."""
    id: str
    device_id: str
    device_name: str
    platform: str
    agent_version: str
    user_id: str
    status: str
    capabilities: list[str]
    registered_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("registered_at", "last_seen_at", "revoked_at", "created_at")
    def _serialize_dt(self, value: datetime | None) -> str | None:
        return _ensure_utc_z(value)


class DeviceHeartbeatRequest(BaseModel):
    """Agent heartbeat payload."""
    device_id: str
    agent_version: str
    jobs_available: int = 0


class DeviceHeartbeatResponse(BaseModel):
    """Cloud response to agent heartbeat."""
    status: str
    pending_jobs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Local Agent — Project Authorization (LA3)
# ---------------------------------------------------------------------------

class DeviceProjectCreate(BaseModel):
    """Request to register a device-project."""
    device_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    local_root_fingerprint: str | None = None
    project_authorization_token: str = Field(min_length=1, max_length=255)


class DeviceProjectResponse(BaseModel):
    """Device-project registration response."""
    id: str
    device_id: str
    user_id: str
    display_name: str
    local_root_fingerprint: str | None
    status: str
    authority: str
    registered_at: datetime
    revoked_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("registered_at", "revoked_at", "created_at")
    def _serialize_dt(self, value: datetime | None) -> str | None:
        return _ensure_utc_z(value)


class ProjectAuthorizationTokenCreate(BaseModel):
    """Request to create a project authorization token."""
    device_id: str = Field(min_length=1, max_length=128)


class ProjectAuthorizationTokenResponse(BaseModel):
    """Response containing a single-use project authorization token."""
    project_authorization_token: str
    expires_at: datetime

    @field_serializer("expires_at")
    def _serialize_dt(self, value: datetime) -> str:
        return _ensure_utc_z(value)


# ---------------------------------------------------------------------------
# Browser-Assisted Pairing (P3c)
# ---------------------------------------------------------------------------

class PairingRequestCreate(BaseModel):
    """Connector creates a pairing request (no auth required)."""
    device_name: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=50)
    agent_version: str = Field(min_length=1, max_length=50)


class PairingRequestResponse(BaseModel):
    """Response containing pairing request identifier for browser URL."""
    pairing_id: str
    pairing_url: str
    expires_at: datetime

    @field_serializer("expires_at")
    def _serialize_dt(self, value: datetime) -> str:
        return _ensure_utc_z(value)


class PairingStatusResponse(BaseModel):
    """Connector polls pairing status."""
    pairing_id: str
    status: str  # PENDING, APPROVED, CONSUMED, EXPIRED, DENIED
    device_credential: str | None = None
    device_id: str | None = None
    expires_at: datetime

    @field_serializer("expires_at")
    def _serialize_dt(self, value: datetime) -> str:
        return _ensure_utc_z(value)


class PairingApprovalRequest(BaseModel):
    """User approves a pairing request in browser."""
    pairing_id: str


class PairingDenialRequest(BaseModel):
    """User denies a pairing request in browser."""
    pairing_id: str


class PairingApprovalResponse(BaseModel):
    """Response after approving/denying a pairing request."""
    pairing_id: str
    status: str
    device_name: str | None = None


# ---------------------------------------------------------------------------
# Local Agent — Governed Scan Jobs (LA4) — Control Plane
# ---------------------------------------------------------------------------

# Allowed operation types — only PROJECT_SCAN for LA4
ALLOWED_OPERATION_TYPES = frozenset({"PROJECT_SCAN"})

# Allowed job statuses
JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_STARTED = "STARTED"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_FAILED = "FAILED"
JOB_STATUS_EXPIRED = "EXPIRED"

VALID_JOB_STATUSES = frozenset({
    JOB_STATUS_PENDING, JOB_STATUS_STARTED,
    JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, JOB_STATUS_EXPIRED,
})


class AgentScanJobCreate(BaseModel):
    """Request to create a governed PROJECT_SCAN job.

    Only the operation type is accepted — no arbitrary commands, paths,
    scripts, or shell instructions.
    """
    operation_type: str = Field(
        default="PROJECT_SCAN",
        pattern=r"^PROJECT_SCAN$",
    )


class AgentJobResponse(BaseModel):
    """Job representation returned to agents and control plane."""
    id: str
    user_id: str
    device_id: str
    device_project_id: str
    operation_type: str
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    truncated: bool = False

    class Config:
        from_attributes = True

    @field_serializer("created_at", "started_at", "completed_at", "failed_at")
    def _serialize_dt(self, value: datetime | None) -> str | None:
        return _ensure_utc_z(value)


class AgentJobStartedRequest(BaseModel):
    """Agent reports job started."""
    agent_version: str = Field(min_length=1, max_length=50)


class AgentJobResultsRequest(BaseModel):
    """Agent submits governed scan results."""
    evidence: dict[str, Any]
    duration_seconds: float = Field(ge=0)


class AgentJobFailedRequest(BaseModel):
    """Agent reports job failure."""
    failure_reason: str = Field(min_length=1, max_length=1000)


# ---------------------------------------------------------------------------
# Local Agent — Governed Scan Jobs (LA4) — Evidence Schema
# ---------------------------------------------------------------------------

class ScanEvidence(BaseModel):
    """Bounded evidence schema for PROJECT_SCAN results."""
    job_id: str
    device_id: str
    device_project_id: str
    project_display_name: str
    agent_version: str
    started_at: str
    completed_at: str
    file_count: int
    languages: list[str]
    project_structure_summary: dict[str, Any]
    git_metadata: dict[str, Any] | None = None
    findings: list[dict[str, Any]]
    truncated: bool
    limits: dict[str, Any]
    provenance: str = "LIVE_EVOSIA_EVIDENCE"
    evidence_source: str = "device_local_scan"


# ---------------------------------------------------------------------------
# Browser-Assisted Project Authorization (P3d)
# ---------------------------------------------------------------------------

class ProjectAuthorizationRequestCreate(BaseModel):
    """Connector creates a project authorization request (requires device JWT)."""
    display_name: str = Field(min_length=1, max_length=255)
    local_root_fingerprint: str = Field(min_length=1, max_length=128)
    platform: str = Field(min_length=1, max_length=50)
    agent_version: str = Field(min_length=1, max_length=50)


class ProjectAuthorizationRequestResponse(BaseModel):
    """Response containing project authorization request identifier for browser URL."""
    request_id: str
    authorization_url: str
    expires_at: datetime

    @field_serializer("expires_at")
    def _serialize_dt(self, value: datetime) -> str:
        return _ensure_utc_z(value)


class ProjectAuthorizationStatusResponse(BaseModel):
    """Response for project authorization status polling."""
    request_id: str
    status: str
    device_project_id: str | None = None
    expires_at: datetime

    @field_serializer("expires_at")
    def _serialize_dt(self, value: datetime) -> str:
        return _ensure_utc_z(value)


class ProjectAuthorizationApprovalResponse(BaseModel):
    """Response for project authorization approval/denial."""
    request_id: str
    status: str
    display_name: str
