"""Morning Brief and Trust Metrics router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import MorningBrief, TrustMetrics, DailyMetrics
from ..services import get_current_user
from ..services.morning_brief import generate_morning_brief
from ..services.trust_service import calculate_trust_metrics
from ..services.metrics_service import collect_daily_metrics
from datetime import datetime, timezone

router = APIRouter()


@router.get("/morning-brief", response_model=MorningBrief)
def morning_brief(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MorningBrief:
    return generate_morning_brief(db)


@router.get("/trust-metrics", response_model=TrustMetrics)
def trust_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrustMetrics:
    return calculate_trust_metrics(db)


@router.get("/daily-metrics/{date}", response_model=DailyMetrics)
def daily_metrics(
    date: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyMetrics:
    return collect_daily_metrics(db, date)
