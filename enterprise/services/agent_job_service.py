"""Agent job service — governed scan job lifecycle management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import (
    AgentJob,
    AgentJobIdempotencyKey,
    Device,
    DeviceProject,
    Finding,
    Report,
    ScanJob,
)
from ..schemas import (
    ALLOWED_OPERATION_TYPES,
    JOB_ACTIVE_STATUSES,
    JOB_STATUS_QUEUED,
    JOB_STATUS_LEGACY_PENDING,
    JOB_STATUS_LEGACY_STARTED,
    JOB_STATUS_PENDING,
    JOB_STATUS_STARTED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PARTIAL,
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCELLED,
)


def create_scan_job(
    db: Session,
    user_id: str,
    device_id: str,
    device_project_id: str,
    operation_type: str = "PROJECT_SCAN",
    idempotency_key: str | None = None,
) -> tuple[AgentJob, bool]:
    """Create a governed PROJECT_SCAN job.

    Called by authenticated user via control plane.
    Validates:
    - user owns the device
    - device is active
    - device project is active
    - operation type is allowed
    - project authority permits REVIEW_ONLY scanning
    """
    # Serialize requests per project. PostgreSQL uses a row lock; SQLite needs
    # an immediate write transaction because it does not implement row locks.
    if db.get_bind().dialect.name == "sqlite":
        db.commit()
        db.execute(text("BEGIN IMMEDIATE"))

    project_query = db.query(DeviceProject).filter(DeviceProject.id == device_project_id)
    if db.get_bind().dialect.name != "sqlite":
        project_query = project_query.with_for_update()
    project = project_query.first()

    # Validate operation type
    if operation_type not in ALLOWED_OPERATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operation type not allowed: {operation_type}",
        )

    # Verify device exists and belongs to user
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    if device.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device does not belong to this user",
        )
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is {device.status}",
        )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device project not found",
        )
    if project.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project does not belong to this device",
        )
    if project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project is {project.status}",
        )
    if project.authority != "REVIEW_ONLY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project authority does not permit scanning: {project.authority}",
        )

    if idempotency_key:
        previous_key = db.query(AgentJobIdempotencyKey).filter(
            AgentJobIdempotencyKey.user_id == user_id,
            AgentJobIdempotencyKey.device_project_id == device_project_id,
            AgentJobIdempotencyKey.idempotency_key == idempotency_key,
        ).first()
        if previous_key:
            db.commit()
            return db.get(AgentJob, previous_key.agent_job_id), False

        legacy_request = db.query(AgentJob).filter(
            AgentJob.user_id == user_id,
            AgentJob.device_project_id == device_project_id,
            AgentJob.idempotency_key == idempotency_key,
        ).first()
        if legacy_request:
            db.add(AgentJobIdempotencyKey(
                user_id=user_id,
                device_project_id=device_project_id,
                idempotency_key=idempotency_key,
                agent_job_id=legacy_request.id,
            ))
            db.commit()
            return legacy_request, False

    # Return the active review for retries/double-clicks rather than creating
    # a second review or turning a successful repeated request into an error.
    active_job = db.query(AgentJob).filter(
        AgentJob.device_project_id == device_project_id,
        AgentJob.operation_type.in_(ALLOWED_OPERATION_TYPES),
        AgentJob.status.in_(JOB_ACTIVE_STATUSES),
    ).order_by(AgentJob.created_at.asc()).first()
    if active_job:
        if idempotency_key:
            db.add(AgentJobIdempotencyKey(
                user_id=user_id,
                device_project_id=device_project_id,
                idempotency_key=idempotency_key,
                agent_job_id=active_job.id,
            ))
        db.commit()
        return active_job, False

    job = AgentJob(
        user_id=user_id,
        device_id=device_id,
        device_project_id=device_project_id,
        operation_type=operation_type,
        status=JOB_STATUS_QUEUED,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    db.flush()
    if idempotency_key:
        db.add(AgentJobIdempotencyKey(
            user_id=user_id,
            device_project_id=device_project_id,
            idempotency_key=idempotency_key,
            agent_job_id=job.id,
        ))
    db.commit()
    db.refresh(job)
    return job, True


def list_jobs_for_project(
    db: Session,
    device_project_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentJob]:
    """List agent jobs for a device project, newest first."""
    return (
        db.query(AgentJob)
        .filter(AgentJob.device_project_id == device_project_id)
        .order_by(AgentJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_next_job(db: Session, device_id: str) -> AgentJob | None:
    """Get the next pending job for a device.

    Called by device via agent work plane.
    Validates device is active.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device or device.status != "active":
        return None

    job = db.query(AgentJob).filter(
        AgentJob.device_id == device_id,
        AgentJob.status.in_((JOB_STATUS_QUEUED, JOB_STATUS_LEGACY_PENDING)),
        AgentJob.operation_type.in_(ALLOWED_OPERATION_TYPES),
    ).order_by(AgentJob.created_at.asc()).first()

    return job


def get_job(db: Session, job_id: str, device_id: str) -> AgentJob:
    """Get a specific job, validating device assignment.

    Raises HTTPException if job not found or doesn't belong to device.
    """
    job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    if job.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Job does not belong to this device",
        )
    return job


def mark_job_started(db: Session, job: AgentJob) -> AgentJob:
    """Mark a job as started.

    Only allowed for PENDING jobs.
    """
    if job.status not in (JOB_STATUS_PENDING, JOB_STATUS_LEGACY_PENDING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is already {job.status}",
        )
    job.status = JOB_STATUS_STARTED
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job: AgentJob,
    evidence: dict,
    duration_seconds: float,
) -> AgentJob:
    """Persist the review and all linked evidence atomically."""
    if job.status in (JOB_STATUS_COMPLETED, JOB_STATUS_PARTIAL):
        if job.evidence == evidence:
            return job
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Review results were already submitted with different evidence",
        )
    if job.status not in (JOB_STATUS_STARTED, JOB_STATUS_LEGACY_STARTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job.status}, expected RUNNING",
        )

    coverage = {
        "files_discovered": evidence["files_discovered"],
        "files_examined": evidence["files_examined"],
        "files_skipped": evidence["files_skipped"],
        "skip_reasons": evidence["skip_reasons"],
        "limits_reached": evidence["limits_reached"],
        "limits": evidence["limits"],
        "started_at": evidence["started_at"],
        "finished_at": evidence["completed_at"],
    }
    partial = bool(evidence["limits_reached"] or evidence["truncated"])
    final_status = JOB_STATUS_PARTIAL if partial else JOB_STATUS_COMPLETED
    finished_at = datetime.now(timezone.utc)
    started_at = datetime.fromisoformat(evidence["started_at"].replace("Z", "+00:00"))
    evidence_finished_at = datetime.fromisoformat(evidence["completed_at"].replace("Z", "+00:00"))
    findings_data = evidence["findings"]
    findings_count = len(findings_data)

    scan = ScanJob(
        id=job.id,
        repository_id=None,
        review_id=job.id,
        status="partial" if partial else "completed",
        scan_type="computer_review",
        started_at=started_at,
        completed_at=evidence_finished_at,
        duration_seconds=duration_seconds,
        findings_count=findings_count,
        requested_by=job.user.email if job.user else None,
        metadata_json={
            "evidence_source": "device_local_scan",
            "provenance": "LIVE_EVOSIA_EVIDENCE",
            "device_id": job.device_id,
            "device_project_id": job.device_project_id,
            "project_display_name": evidence["project_display_name"],
            "coverage": coverage,
        },
    )
    db.add(scan)

    persisted_findings = []
    for item in findings_data:
        kind = str(item.get("type") or item.get("finding_type") or "PROJECT_REVIEW")[:100]
        path = str(item.get("path") or "")[:512]
        title = kind.replace("_", " ").title()
        if path:
            title = f"{title}: {path}"
        severity = str(item.get("severity") or "low").lower()
        if severity not in {"critical", "high", "medium", "low"}:
            severity = "low"
        description = item.get("description") or item.get("classification") or kind
        finding = Finding(
            repository_id=None,
            review_id=job.id,
            scan_job_id=job.id,
            finding_type=kind,
            severity=severity,
            category=str(item.get("category") or "project_review")[:100],
            title=title[:512],
            description=str(description),
            module=path or None,
            status="open",
            metadata_json=item,
        )
        db.add(finding)
        persisted_findings.append(item)

    summary = (
        f"Review of {evidence['project_display_name']} examined "
        f"{coverage['files_examined']} of {coverage['files_discovered']} discovered files "
        f"and produced {findings_count} finding(s)."
    )
    if partial:
        summary += " Completed with limits."
    report = Report(
        review_id=job.id,
        title=f"Computer review: {evidence['project_display_name']}",
        status="PARTIAL" if partial else "COMPLETED",
        summary=summary,
        report_data={
            "review_id": job.id,
            "project_display_name": evidence["project_display_name"],
            "findings": persisted_findings,
            "coverage": coverage,
            "languages": evidence["languages"],
            "provenance": "LIVE_EVOSIA_EVIDENCE",
            "evidence_source": "device_local_scan",
        },
        duration_seconds=duration_seconds,
        tasks_planned=coverage["files_discovered"],
        tasks_completed=coverage["files_examined"],
        tasks_failed=coverage["files_skipped"],
    )
    db.add(report)
    job.status = final_status
    job.completed_at = finished_at
    job.truncated = partial
    job.evidence = evidence
    job.coverage = coverage
    db.commit()
    db.refresh(job)
    return job


def fail_job(db: Session, job: AgentJob, reason: str) -> AgentJob:
    """Mark a job as failed.

    Only allowed for PENDING or STARTED jobs.
    """
    if job.status not in (
        JOB_STATUS_PENDING,
        JOB_STATUS_STARTED,
        JOB_STATUS_LEGACY_PENDING,
        JOB_STATUS_LEGACY_STARTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job.status}, cannot mark as failed",
        )
    job.status = JOB_STATUS_FAILED
    job.failed_at = datetime.now(timezone.utc)
    job.failure_reason = reason
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job: AgentJob) -> AgentJob:
    """Persist cancellation of queued/running work."""
    if job.status in (JOB_STATUS_COMPLETED, JOB_STATUS_PARTIAL, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED):
        return job
    if job.status not in (
        JOB_STATUS_PENDING,
        JOB_STATUS_STARTED,
        JOB_STATUS_LEGACY_PENDING,
        JOB_STATUS_LEGACY_STARTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job.status}, cannot cancel",
        )
    job.status = JOB_STATUS_CANCELLED
    job.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
