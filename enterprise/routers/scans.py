"""Scan Jobs router — create, start, cancel, retry, and monitor repository scans."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AgentJob, Repository, ScanJob, ScanHistory, User
from ..schemas import ScanJobCreate, ScanJobResponse, ScanJobQuery, ScanHistoryResponse
from ..services import get_current_user
from ..services.scanner import (
    create_scan_job, start_scan, cancel_scan, retry_scan, list_scan_jobs,
)

router = APIRouter()


def _get_owned_scan(db: Session, scan_id: str, user: User) -> ScanJob | None:
    return (
        db.query(ScanJob)
        .outerjoin(AgentJob, ScanJob.review_id == AgentJob.id)
        .outerjoin(Repository, ScanJob.repository_id == Repository.id)
        .filter(
            ScanJob.id == scan_id,
            or_(
                and_(ScanJob.review_id.is_not(None), AgentJob.user_id == user.id),
                and_(ScanJob.review_id.is_(None), Repository.owner_user_id == user.id),
            ),
        )
        .first()
    )


@router.get("", response_model=list[ScanJobResponse])
def list_jobs(
    repository_id: str | None = None,
    status: str | None = None,
    scan_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScanJob]:
    q = (
        db.query(ScanJob)
        .outerjoin(AgentJob, ScanJob.review_id == AgentJob.id)
        .outerjoin(Repository, ScanJob.repository_id == Repository.id)
        .filter(
            or_(
                and_(ScanJob.review_id.is_not(None), AgentJob.user_id == user.id),
                and_(ScanJob.review_id.is_(None), Repository.owner_user_id == user.id),
            )
        )
    )
    if repository_id:
        q = q.filter(ScanJob.repository_id == repository_id)
    if status:
        q = q.filter(ScanJob.status == status)
    if scan_type:
        q = q.filter(ScanJob.scan_type == scan_type)
    return q.order_by(ScanJob.created_at.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=ScanJobResponse, status_code=201)
def create_job(
    body: ScanJobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanJob:
    repository = db.query(Repository).filter(
        Repository.id == body.repository_id,
        Repository.owner_user_id == user.id,
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    try:
        job = create_scan_job(db, body.repository_id, body.scan_type, body.branch, requested_by=user.email)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return job


@router.post("/{job_id}/start", response_model=ScanJobResponse)
def start_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanJob:
    scan = _get_owned_scan(db, job_id, user)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if scan.review_id:
        raise HTTPException(
            status_code=409,
            detail="Computer reviews cannot be started as repository scans",
        )
    try:
        job = start_scan(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return job


@router.post("/{job_id}/cancel", response_model=ScanJobResponse)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanJob:
    job = _get_owned_scan(db, job_id, user)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if job.review_id:
        raise HTTPException(
            status_code=409,
            detail="Computer reviews must be cancelled from the Computers page",
        )
    try:
        job = cancel_scan(db, job_id, requested_by=user.email)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return job


@router.post("/{job_id}/retry", response_model=ScanJobResponse, status_code=201)
def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanJob:
    job = _get_owned_scan(db, job_id, user)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if job.review_id:
        raise HTTPException(
            status_code=409,
            detail="Computer reviews cannot be retried as repository scans",
        )
    try:
        job = retry_scan(db, job_id, requested_by=user.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return job


@router.get("/{job_id}", response_model=ScanJobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanJob:
    job = _get_owned_scan(db, job_id, user)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job


@router.get("/{job_id}/history", response_model=list[ScanHistoryResponse])
def get_job_history(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScanHistory]:
    job = _get_owned_scan(db, job_id, user)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return (
        db.query(ScanHistory)
        .filter(ScanHistory.scan_job_id == job_id)
        .order_by(ScanHistory.created_at.asc())
        .all()
    )
