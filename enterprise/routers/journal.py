"""Journal router — query engineering journal events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import JournalEvent, User
from ..schemas import JournalEventResponse
from ..services import get_current_user

router = APIRouter()


@router.get("", response_model=list[JournalEventResponse])
def list_events(
    event_type: str | None = None,
    stage: str | None = None,
    repository_id: str | None = None,
    actor: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[JournalEvent]:
    q = db.query(JournalEvent)
    if event_type:
        q = q.filter(JournalEvent.event_type == event_type)
    if stage:
        q = q.filter(JournalEvent.stage == stage)
    if repository_id:
        q = q.filter(JournalEvent.repository_id == repository_id)
    if actor:
        q = q.filter(JournalEvent.actor == actor)
    if after:
        q = q.filter(JournalEvent.timestamp > after)
    if before:
        q = q.filter(JournalEvent.timestamp < before)
    return q.order_by(JournalEvent.timestamp.desc()).offset(offset).limit(limit).all()


@router.get("/{event_id}", response_model=JournalEventResponse)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> JournalEvent:
    event = db.query(JournalEvent).filter(JournalEvent.event_id == event_id).first()
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")
    return event
