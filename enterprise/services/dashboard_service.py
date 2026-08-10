"""Dashboard Service — aggregation logic for dashboard and overnight APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Repository, Finding, Mission, ScanJob, JournalEvent


def get_dashboard_activity(
    db: Session,
    since: datetime | None = None,
) -> dict:
    """Aggregate dashboard activity metrics."""
    if since is None:
        since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    repos_total = db.query(func.count(Repository.id)).scalar() or 0
    repos_ready = db.query(func.count(Repository.id)).filter(
        Repository.status == "active"
    ).scalar() or 0
    repos_blocked = db.query(func.count(Repository.id)).filter(
        Repository.status == "blocked"
    ).scalar() or 0

    scans_queued = db.query(func.count(ScanJob.id)).filter(
        ScanJob.status.in_(["pending", "queued"])
    ).scalar() or 0
    scans_running = db.query(func.count(ScanJob.id)).filter(
        ScanJob.status == "running"
    ).scalar() or 0
    scans_completed_since = db.query(func.count(ScanJob.id)).filter(
        ScanJob.status == "completed",
        ScanJob.completed_at >= since,
    ).scalar() or 0
    scans_failed_since = db.query(func.count(ScanJob.id)).filter(
        ScanJob.status == "failed",
        ScanJob.completed_at >= since,
    ).scalar() or 0

    new_findings_since = db.query(func.count(Finding.id)).filter(
        Finding.created_at >= since,
    ).scalar() or 0

    gov_approved = db.query(func.count(JournalEvent.id)).filter(
        JournalEvent.event_type == "recommendation.approved",
        JournalEvent.created_at >= since,
    ).scalar() or 0
    gov_rejected = db.query(func.count(JournalEvent.id)).filter(
        JournalEvent.event_type == "recommendation.rejected",
        JournalEvent.created_at >= since,
    ).scalar() or 0

    draft_missions = db.query(func.count(Mission.id)).filter(
        Mission.status == "pending",
        Mission.created_at >= since,
    ).scalar() or 0

    ci_failures = db.query(func.count(JournalEvent.id)).filter(
        JournalEvent.event_type == "mission.failed",
        JournalEvent.created_at >= since,
    ).scalar() or 0

    latest_events = (
        db.query(JournalEvent)
        .order_by(JournalEvent.created_at.desc())
        .limit(20)
        .all()
    )

    avg_health = db.query(func.avg(Repository.health_score)).scalar()

    return {
        "repositories_total": repos_total,
        "repositories_ready": repos_ready,
        "repositories_blocked": repos_blocked,
        "scans_queued": scans_queued,
        "scans_running": scans_running,
        "scans_completed_since": scans_completed_since,
        "scans_failed_since": scans_failed_since,
        "new_findings_since": new_findings_since,
        "governance_approved_since": gov_approved,
        "governance_rejected_since": gov_rejected,
        "draft_missions_since": draft_missions,
        "ci_failures_since": ci_failures,
        "latest_activity": latest_events,
        "average_repository_health": round(avg_health, 1) if avg_health is not None else None,
    }


def get_overnight_summary(
    db: Session,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict:
    """Generate overnight activity summary."""
    now = datetime.now(timezone.utc)
    if window_end is None:
        window_end = now
    if window_start is None:
        window_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=12)

    repos_scanned = db.query(func.count(func.distinct(ScanJob.repository_id))).filter(
        ScanJob.started_at >= window_start,
        ScanJob.started_at <= window_end,
    ).scalar() or 0

    blocked_repos = db.query(func.count(Repository.id)).filter(
        Repository.status == "blocked"
    ).scalar() or 0

    successful_scans = db.query(func.count(ScanJob.id)).filter(
        ScanJob.status == "completed",
        ScanJob.completed_at >= window_start,
        ScanJob.completed_at <= window_end,
    ).scalar() or 0

    failed_scans = db.query(func.count(ScanJob.id)).filter(
        ScanJob.status == "failed",
        ScanJob.completed_at >= window_start,
        ScanJob.completed_at <= window_end,
    ).scalar() or 0

    new_findings = db.query(func.count(Finding.id)).filter(
        Finding.created_at >= window_start,
        Finding.created_at <= window_end,
    ).scalar() or 0

    resolved_findings = db.query(func.count(Finding.id)).filter(
        Finding.status == "resolved",
        Finding.updated_at >= window_start,
        Finding.updated_at <= window_end,
    ).scalar() or 0

    governance_decisions = db.query(func.count(JournalEvent.id)).filter(
        JournalEvent.event_type.in_(["governance.decided", "recommendation.approved", "recommendation.rejected"]),
        JournalEvent.created_at >= window_start,
        JournalEvent.created_at <= window_end,
    ).scalar() or 0

    draft_missions = db.query(func.count(Mission.id)).filter(
        Mission.status == "pending",
        Mission.created_at >= window_start,
        Mission.created_at <= window_end,
    ).scalar() or 0

    ci_failures = db.query(func.count(JournalEvent.id)).filter(
        JournalEvent.event_type == "mission.failed",
        JournalEvent.created_at >= window_start,
        JournalEvent.created_at <= window_end,
    ).scalar() or 0

    # Top repos requiring attention: repos with recent failures or blocked status
    attention_repos = []
    failed_repo_ids = (
        db.query(ScanJob.repository_id)
        .filter(
            ScanJob.status == "failed",
            ScanJob.completed_at >= window_start,
        )
        .distinct()
        .limit(5)
        .all()
    )
    for (repo_id,) in failed_repo_ids:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if repo:
            attention_repos.append({
                "id": repo.id,
                "name": repo.name,
                "reason": "recent_scan_failure",
            })

    blocked_repos_list = (
        db.query(Repository)
        .filter(Repository.status == "blocked")
        .limit(5)
        .all()
    )
    for repo in blocked_repos_list:
        if not any(r["id"] == repo.id for r in attention_repos):
            attention_repos.append({
                "id": repo.id,
                "name": repo.name,
                "reason": "blocked",
            })

    parts = []
    if successful_scans:
        parts.append(f"{successful_scans} scan(s) completed successfully")
    if failed_scans:
        parts.append(f"{failed_scans} scan(s) failed")
    if new_findings:
        parts.append(f"{new_findings} new finding(s) discovered")
    if governance_decisions:
        parts.append(f"{governance_decisions} governance decision(s) made")
    if draft_missions:
        parts.append(f"{draft_missions} mission(s) drafted")
    summary = "; ".join(parts) if parts else "No significant activity during this window"

    return {
        "window_start": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_end": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repositories_scanned": repos_scanned,
        "blocked_repositories": blocked_repos,
        "successful_scans": successful_scans,
        "failed_scans": failed_scans,
        "new_findings": new_findings,
        "resolved_findings": resolved_findings,
        "governance_decisions": governance_decisions,
        "draft_missions": draft_missions,
        "ci_failures": ci_failures,
        "top_repositories_requiring_attention": attention_repos,
        "summary": summary,
    }
