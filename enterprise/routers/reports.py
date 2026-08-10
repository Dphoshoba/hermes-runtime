"""Reports router — query mission reports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Report, User
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
    _user: User = Depends(get_current_user),
) -> list[Report]:
    q = db.query(Report)
    if repository_id:
        q = q.filter(Report.repository_id == repository_id)
    if status:
        q = q.filter(Report.status == status)
    return q.order_by(Report.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Report:
    from fastapi import HTTPException
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
