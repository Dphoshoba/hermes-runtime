"""Friction Journal router — record operational friction during trial."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, FrictionRecord
from ..schemas import FrictionCreate, FrictionResponse
from ..services import get_current_user
from ..services.trial_service import get_active_trial

router = APIRouter()


@router.post("", response_model=FrictionResponse, status_code=201)
def record_friction(
    body: FrictionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FrictionResponse:
    trial = get_active_trial(db)
    if not trial:
        raise HTTPException(status_code=400, detail="No active trial")
    record = FrictionRecord(
        trial_id=trial.trial_id,
        timestamp=datetime.now(timezone.utc),
        repository_id=body.repository_id,
        category=body.category,
        severity=body.severity,
        description=body.description,
        workaround=body.workaround,
        related_scan_id=body.related_scan_id,
        related_finding_id=body.related_finding_id,
        related_mission_id=body.related_mission_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[FrictionResponse])
def list_friction(
    trial_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FrictionResponse]:
    q = db.query(FrictionRecord)
    if trial_id:
        q = q.filter(FrictionRecord.trial_id == trial_id)
    if category:
        q = q.filter(FrictionRecord.category == category)
    if severity:
        q = q.filter(FrictionRecord.severity == severity)
    return q.order_by(FrictionRecord.created_at.desc()).limit(limit).all()
