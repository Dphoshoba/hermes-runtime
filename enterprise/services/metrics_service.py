"""Daily operational metrics aggregation from existing data."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone, timedelta
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    Repository, ScanJob, Finding, Mission, JournalEvent, OperatorFeedback,
    FrictionRecord, FindingAdjudication,
)
from ..schemas import DailyMetrics


def _day_range(date_str: str) -> tuple[datetime, datetime]:
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def collect_daily_metrics(db: Session, date_str: str) -> DailyMetrics:
    start, end = _day_range(date_str)

    repos_total = db.query(func.count(Repository.id)).scalar() or 0
    repos_blocked = db.query(func.count(Repository.id)).filter(Repository.status == "blocked").scalar() or 0

    scans_that_day = db.query(ScanJob).filter(
        ScanJob.created_at >= start, ScanJob.created_at < end
    ).all()

    successful = sum(1 for s in scans_that_day if s.status == "completed")
    failed = sum(1 for s in scans_that_day if s.status == "failed")
    cancelled = sum(1 for s in scans_that_day if s.status == "cancelled")
    retried = sum(1 for s in scans_that_day if s.attempt and s.attempt > 1)
    repos_scanned = len({s.repository_id for s in scans_that_day if s.status == "completed"})

    durations = [s.duration_seconds for s in scans_that_day if s.duration_seconds is not None]
    avg_duration = statistics.mean(durations) if durations else None
    p50_duration = statistics.median(durations) if durations else None
    p95_duration = (sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 2 else avg_duration) if durations else None

    stage_times: dict[str, list[float]] = {}
    for s in scans_that_day:
        if s.stage_timings:
            for stage, timing in s.stage_timings.items():
                if isinstance(timing, dict) and "duration_seconds" in timing:
                    stage_times.setdefault(stage, []).append(timing["duration_seconds"])
    slowest_stage = max(stage_times, key=lambda k: statistics.mean(stage_times[k])) if stage_times else None

    findings_that_day = db.query(Finding).filter(
        Finding.created_at >= start, Finding.created_at < end
    ).all()
    findings_new = len(findings_that_day)

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for f in findings_that_day:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        by_category[f.category] = by_category.get(f.category, 0) + 1

    feedback = db.query(OperatorFeedback).filter(
        OperatorFeedback.created_at >= start, OperatorFeedback.created_at < end
    ).all()
    fp_count = sum(1 for f in feedback if f.classification == "FALSE_POSITIVE")
    useful_count = sum(1 for f in feedback if f.classification == "USEFUL")

    missions_that_day = db.query(Mission).filter(
        Mission.created_at >= start, Mission.created_at < end
    ).all()
    missions_gen = len(missions_that_day)
    missions_approved = sum(1 for m in missions_that_day if m.status == "approved")
    missions_rejected = sum(1 for m in missions_that_day if m.status == "rejected")

    governance_events = db.query(JournalEvent).filter(
        JournalEvent.event_type.like("%governance%"),
        JournalEvent.timestamp >= start.isoformat(),
        JournalEvent.timestamp < end.isoformat(),
    ).all()
    gov_approved = sum(1 for e in governance_events if "approved" in (e.payload or {}).get("decision", ""))
    gov_rejected = sum(1 for e in governance_events if "rejected" in (e.payload or {}).get("decision", ""))
    gov_needs = sum(1 for e in governance_events if "needs" in (e.payload or {}).get("decision", ""))
    gov_dup = sum(1 for e in governance_events if "duplicate" in (e.payload or {}).get("decision", ""))

    friction = db.query(FrictionRecord).filter(
        FrictionRecord.created_at >= start, FrictionRecord.created_at < end
    ).count()

    return DailyMetrics(
        date=date_str,
        repositories_registered=repos_total,
        repositories_scanned=repos_scanned,
        successful_scans=successful,
        failed_scans=failed,
        blocked_repositories=repos_blocked,
        cancelled_scans=cancelled,
        retried_scans=retried,
        findings_generated=findings_new,
        findings_new=findings_new,
        findings_resolved=None,
        findings_by_severity=by_severity,
        findings_by_category=by_category,
        governance_approved=gov_approved,
        governance_rejected=gov_rejected,
        governance_needs_evidence=gov_needs,
        governance_duplicate=gov_dup,
        missions_generated=missions_gen,
        missions_approved=missions_approved,
        missions_rejected=missions_rejected,
        false_positives_confirmed=fp_count,
        useful_findings_confirmed=useful_count,
        unsafe_recommendations_detected=0,
        evidence_quality_issues=0,
        average_scan_duration=avg_duration,
        p50_scan_duration=p50_duration,
        p95_scan_duration=p95_duration,
        slowest_pipeline_stage=slowest_stage,
        api_failures=failed,
        ui_failures=0,
        journal_integrity_failures=0,
    )


# ---------------------------------------------------------------------------
# Evidence & Risk Gate metrics (Post Cycle 8)
# DEPRECATED: governance_approval_rate — do not optimize around it.
# These metrics replace raw approval rate as the primary quality signal.
# ---------------------------------------------------------------------------

def collect_gate_metrics(db: Session, repository_id: str | None = None) -> dict[str, Any]:
    """Compute Evidence & Risk Gate operating metrics.

    Replaces the deprecated governance_approval_rate. Surfaces human-usefulness,
    evidence sufficiency, review burden, and unsafe-automation (pinned 0).
    """
    q = db.query(FindingAdjudication)
    if repository_id:
        q = q.filter(FindingAdjudication.repository_id == repository_id)
    adjs = q.all()

    from ..models import Finding
    finding_q = db.query(Finding)
    if repository_id:
        finding_q = finding_q.filter(Finding.repository_id == repository_id)
    total_findings = finding_q.count()

    counts: dict[str, int] = {}
    actionable = 0
    not_actionable = 0
    nme = 0
    dup = 0
    useful = 0
    for a in adjs:
        counts[a.classification] = counts.get(a.classification, 0) + 1
        if a.classification == "ACTIONABLE":
            actionable += 1
        elif a.classification == "NOT_ACTIONABLE":
            not_actionable += 1
        elif a.classification == "NEEDS_MORE_EVIDENCE":
            nme += 1
        elif a.classification == "DUPLICATE":
            dup += 1
        elif a.classification == "USEFUL":
            useful += 1

    suppressions = (
        db.query(FindingAdjudication)
        .filter(FindingAdjudication.policy_suppressed.is_(True))
    )
    if repository_id:
        suppressions = suppressions.filter(FindingAdjudication.repository_id == repository_id)
    suppression_count = suppressions.count()

    reviewed = len(adjs)
    pending_review = max(total_findings - reviewed, 0)

    human_usefulness_rate = (useful / reviewed) if reviewed else None
    human_actionability_rate = (actionable / reviewed) if reviewed else None
    evidence_sufficiency_rate = (
        ((actionable + not_actionable + useful) / reviewed) if reviewed else None
    )
    review_completion_rate = (reviewed / total_findings) if total_findings else None
    suppression_rate = (suppression_count / total_findings) if total_findings else None

    return {
        "total_findings": total_findings,
        "findings_requiring_review": pending_review,
        "reviewed": reviewed,
        "evidence_sufficiency_rate": evidence_sufficiency_rate,
        "human_usefulness_rate": human_usefulness_rate,
        "human_actionability_rate": human_actionability_rate,
        "review_burden": pending_review,
        "review_completion_rate": review_completion_rate,
        "policy_suppression_rate": suppression_rate,
        "useful_finding_retention": useful,
        "mission_eligibility_rate": (actionable / total_findings) if total_findings else None,
        "mission_acceptance_rate": None,  # filled by mission layer
        "mission_traceability_coverage": None,  # filled by mission layer
        "operator_override_rate": None,  # requires reclassification tracking
        "unsafe_automation_rate": 0.0,  # machine gate never emits actionability
        "deprecated_governance_approval_rate": None,  # DO NOT USE
        "adjudication_counts": counts,
        "suppression_count": suppression_count,
    }
