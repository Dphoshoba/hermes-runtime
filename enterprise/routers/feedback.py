"""Operator Feedback router — classify findings during trial."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, OperatorFeedback
from ..schemas import FeedbackCreate, FeedbackResponse
from ..services import get_current_user
from ..services.trial_service import get_active_trial

router = APIRouter()


@router.post("", response_model=FeedbackResponse, status_code=201)
def submit_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackResponse:
    trial = get_active_trial(db)
    if not trial:
        raise HTTPException(status_code=400, detail="No active trial")
    feedback = OperatorFeedback(
        trial_id=trial.trial_id,
        finding_id=body.finding_id,
        repository_id=body.repository_id,
        classification=body.classification,
        notes=body.notes,
        operator=user.email,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    trial_id: str | None = None,
    finding_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FeedbackResponse]:
    q = db.query(OperatorFeedback)
    if trial_id:
        q = q.filter(OperatorFeedback.trial_id == trial_id)
    if finding_id:
        q = q.filter(OperatorFeedback.finding_id == finding_id)
    return q.order_by(OperatorFeedback.created_at.desc()).limit(limit).all()
