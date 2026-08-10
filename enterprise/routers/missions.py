"""Missions router — query mission queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Mission, User
from ..schemas import MissionResponse
from ..services import get_current_user

router = APIRouter()


@router.get("", response_model=list[MissionResponse])
def list_missions(
    repository_id: str | None = None,
    status: str | None = None,
    mission_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Mission]:
    q = db.query(Mission)
    if repository_id:
        q = q.filter(Mission.repository_id == repository_id)
    if status:
        q = q.filter(Mission.status == status)
    if mission_type:
        q = q.filter(Mission.mission_type == mission_type)
    return q.order_by(Mission.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Mission:
    from fastapi import HTTPException
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission
