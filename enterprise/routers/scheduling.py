"""Scheduling router — read-only repository analysis scheduling."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import ScheduleCreate
from ..services import get_current_user
from ..services.scheduler import get_scheduled_repositories, validate_cron
from ..services.safety import check_safety_boundary

router = APIRouter()


@router.get("/repositories")
def scheduled_repositories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return get_scheduled_repositories(db)


@router.post("/validate")
def validate_schedule(
    body: ScheduleCreate,
    user: User = Depends(get_current_user),
) -> dict:
    valid = validate_cron(body.cron_expression)
    safety = check_safety_boundary("scan_repository")
    return {
        "cron_valid": valid,
        "safety_check": safety,
        "repository_id": body.repository_id,
    }
