"""Dashboard router — aggregated stats, activity, and overnight summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Repository, Finding, Mission, Report, JournalEvent, User
from ..schemas import DashboardStats, DashboardActivity, JournalEventResponse, DashboardActivityResponse, OvernightSummaryResponse
from ..services import get_current_user
from ..services.dashboard_service import get_dashboard_activity, get_overnight_summary

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DashboardStats:
    total_repos = db.query(func.count(Repository.id)).scalar() or 0
    active_repos = db.query(func.count(Repository.id)).filter(Repository.status == "active").scalar() or 0

    total_findings = db.query(func.count(Finding.id)).scalar() or 0
    open_findings = db.query(func.count(Finding.id)).filter(Finding.status == "open").scalar() or 0
    critical_findings = db.query(func.count(Finding.id)).filter(Finding.severity == "critical", Finding.status == "open").scalar() or 0
    high_findings = db.query(func.count(Finding.id)).filter(Finding.severity == "high", Finding.status == "open").scalar() or 0

    total_missions = db.query(func.count(Mission.id)).scalar() or 0
    pending_missions = db.query(func.count(Mission.id)).filter(Mission.status == "pending").scalar() or 0
    running_missions = db.query(func.count(Mission.id)).filter(Mission.status == "running").scalar() or 0
    completed_missions = db.query(func.count(Mission.id)).filter(Mission.status == "completed").scalar() or 0
    failed_missions = db.query(func.count(Mission.id)).filter(Mission.status == "failed").scalar() or 0

    total_reports = db.query(func.count(Report.id)).scalar() or 0

    avg_health = db.query(func.avg(Repository.health_score)).scalar()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    journal_today = db.query(func.count(JournalEvent.id)).filter(
        JournalEvent.created_at >= today_start
    ).scalar() or 0

    return DashboardStats(
        total_repositories=total_repos,
        active_repositories=active_repos,
        total_findings=total_findings,
        open_findings=open_findings,
        critical_findings=critical_findings,
        high_findings=high_findings,
        total_missions=total_missions,
        pending_missions=pending_missions,
        running_missions=running_missions,
        completed_missions=completed_missions,
        failed_missions=failed_missions,
        total_reports=total_reports,
        avg_health_score=round(avg_health, 1) if avg_health is not None else None,
        journal_events_today=journal_today,
    )


@router.get("/activity", response_model=DashboardActivity)
def get_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DashboardActivity:
    events = (
        db.query(JournalEvent)
        .order_by(JournalEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    total = db.query(func.count(JournalEvent.id)).scalar() or 0
    return DashboardActivity(events=events, total=total)


@router.get("/activity-v2", response_model=DashboardActivityResponse)
def get_activity_v2(
    since: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None
    return get_dashboard_activity(db, since=since_dt)


@router.get("/overnight", response_model=OvernightSummaryResponse)
def get_overnight(
    window_start: str | None = None,
    window_end: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    start_dt = None
    end_dt = None
    if window_start:
        try:
            start_dt = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
        except ValueError:
            start_dt = None
    if window_end:
        try:
            end_dt = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
        except ValueError:
            end_dt = None
    return get_overnight_summary(db, window_start=start_dt, window_end=end_dt)
