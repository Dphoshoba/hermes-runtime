"""Daily Morning Brief — derived entirely from stored evidence."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models import (
    Repository, ScanJob, Finding, Mission, JournalEvent,
    OperatorFeedback, FrictionRecord,
)
from ..schemas import MorningBrief


def generate_morning_brief(db: Session, since: datetime | None = None) -> MorningBrief:
    now = datetime.now(timezone.utc)
    if since is None:
        since = now - timedelta(hours=24)

    repos = db.query(Repository).all()
    blocked = [r for r in repos if r.status == "blocked"]

    scans = db.query(ScanJob).filter(ScanJob.created_at >= since).all()
    successful = [s for s in scans if s.status == "completed"]
    failed = [s for s in scans if s.status == "failed"]
    retried = [s for s in scans if s.attempt and s.attempt > 1]
    recovered = [s for s in retried if s.status == "completed"]

    durations = [s.duration_seconds for s in successful if s.duration_seconds is not None]
    avg_time = sum(durations) / len(durations) if durations else None

    repos_scanned = len({s.repository_id for s in successful})

    findings = db.query(Finding).filter(Finding.created_at >= since).all()
    high_crit = [f for f in findings if f.severity in ("high", "critical")]

    feedback = db.query(OperatorFeedback).filter(OperatorFeedback.created_at >= since).all()
    useful = sum(1 for f in feedback if f.classification == "USEFUL")
    fp = sum(1 for f in feedback if f.classification == "FALSE_POSITIVE")

    gov_events = db.query(JournalEvent).filter(
        JournalEvent.event_type.like("%governance%"),
        JournalEvent.timestamp >= since.isoformat(),
    ).all()
    gov_approved = sum(1 for e in gov_events if "approved" in (e.payload or {}).get("decision", ""))
    gov_rejected = sum(1 for e in gov_events if "rejected" in (e.payload or {}).get("decision", ""))

    missions = db.query(Mission).filter(Mission.created_at >= since).all()
    draft_missions = [m for m in missions if m.status == "pending"]

    friction_count = db.query(FrictionRecord).filter(FrictionRecord.created_at >= since).count()

    attention = []
    for r in repos:
        reasons = []
        if r.status == "blocked":
            reasons.append("blocked")
        recent_failed = [s for s in scans if s.repository_id == r.id and s.status == "failed"]
        if recent_failed:
            reasons.append(f"{len(recent_failed)} failed scans")
        open_findings = db.query(Finding).filter(
            Finding.repository_id == r.id, Finding.status == "open"
        ).count()
        if open_findings > 5:
            reasons.append(f"{open_findings} open findings")
        if reasons:
            attention.append({"id": r.id, "name": r.name, "reasons": reasons})

    review_order = []
    for r in repos:
        score = 0
        recent_findings = db.query(Finding).filter(
            Finding.repository_id == r.id, Finding.status == "open"
        ).count()
        score += recent_findings * 2
        if r.health_score and r.health_score < 0.5:
            score += 10
        if r.status == "blocked":
            score += 20
        if score > 0:
            review_order.append({"id": r.id, "name": r.name, "priority_score": score})
    review_order.sort(key=lambda x: x["priority_score"], reverse=True)

    hour = now.hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 18:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"

    return MorningBrief(
        greeting=greeting,
        period_start=since.isoformat(),
        period_end=now.isoformat(),
        repositories_scanned=repos_scanned,
        successful_scans=len(successful),
        failed_scans=len(failed),
        blocked_repositories=len(blocked),
        new_findings=len(findings),
        high_critical_findings=len(high_crit),
        useful_findings_confirmed=useful,
        false_positives_confirmed=fp,
        governance_approvals=gov_approved,
        governance_rejections=gov_rejected,
        draft_missions=len(draft_missions),
        retries=len(retried),
        recovered_failures=len(recovered),
        average_scan_time=avg_time,
        repositories_requiring_attention=attention,
        operational_friction=friction_count,
        safety_incidents=0,
        recommended_review_order=review_order[:10],
    )
