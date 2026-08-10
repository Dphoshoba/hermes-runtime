"""Findings router — query engineering findings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Finding, User
from ..schemas import FindingResponse
from ..services import get_current_user

router = APIRouter()


@router.get("", response_model=list[FindingResponse])
def list_findings(
    repository_id: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Finding]:
    q = db.query(Finding)
    if repository_id:
        q = q.filter(Finding.repository_id == repository_id)
    if severity:
        q = q.filter(Finding.severity == severity)
    if category:
        q = q.filter(Finding.category == category)
    if status:
        q = q.filter(Finding.status == status)
    return q.order_by(Finding.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Finding:
    from fastapi import HTTPException
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding
