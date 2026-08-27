"""Agent job service — governed scan job lifecycle management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import AgentJob, Device, DeviceProject
from ..schemas import (
    ALLOWED_OPERATION_TYPES,
    JOB_STATUS_PENDING,
    JOB_STATUS_STARTED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)


def create_scan_job(
    db: Session,
    user_id: str,
    device_id: str,
    device_project_id: str,
    operation_type: str = "PROJECT_SCAN",
) -> AgentJob:
    """Create a governed PROJECT_SCAN job.

    Called by authenticated user via control plane.
    Validates:
    - user owns the device
    - device is active
    - device project is active
    - operation type is allowed
    - project authority permits REVIEW_ONLY scanning
    """
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

    # Verify device project exists and is active
    project = db.query(DeviceProject).filter(
        DeviceProject.id == device_project_id
    ).first()
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

    # Create the job
    job = AgentJob(
        user_id=user_id,
        device_id=device_id,
        device_project_id=device_project_id,
        operation_type=operation_type,
        status=JOB_STATUS_PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
        AgentJob.status == JOB_STATUS_PENDING,
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
    if job.status != JOB_STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is already {job.status}",
        )
    job.status = JOB_STATUS_STARTED
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def complete_job(db: Session, job: AgentJob) -> AgentJob:
    """Mark a job as completed.

    Only allowed for STARTED jobs.
    """
    if job.status != JOB_STATUS_STARTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job.status}, expected STARTED",
        )
    job.status = JOB_STATUS_COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def fail_job(db: Session, job: AgentJob, reason: str) -> AgentJob:
    """Mark a job as failed.

    Only allowed for PENDING or STARTED jobs.
    """
    if job.status not in (JOB_STATUS_PENDING, JOB_STATUS_STARTED):
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
