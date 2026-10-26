"""Reports router — query mission reports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AgentJob, Repository, Report, User
from ..schemas import ReportResponse
from ..services import get_current_user

router = APIRouter()


@router.get("", response_model=list[ReportResponse])
def list_reports(
    repository_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Report]:
    q = (
        db.query(Report)
        .outerjoin(AgentJob, Report.review_id == AgentJob.id)
        .outerjoin(Repository, Report.repository_id == Repository.id)
        .filter(
            or_(
                and_(Report.review_id.is_not(None), AgentJob.user_id == user.id),
                and_(Report.review_id.is_(None), Repository.owner_user_id == user.id),
            )
        )
    )
    if repository_id:
        q = q.filter(Report.repository_id == repository_id)
    if status:
        q = q.filter(Report.status == status)
    return q.order_by(Report.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Report:
    report = (
        db.query(Report)
        .outerjoin(AgentJob, Report.review_id == AgentJob.id)
        .outerjoin(Repository, Report.repository_id == Repository.id)
        .filter(
            Report.id == report_id,
            or_(
                and_(Report.review_id.is_not(None), AgentJob.user_id == user.id),
                and_(Report.review_id.is_(None), Repository.owner_user_id == user.id),
            ),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
