"""Trust metrics calculations from operational data."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import OperatorFeedback, ScanJob, Finding
from ..schemas import TrustMetrics


def calculate_trust_metrics(db: Session, since: datetime | None = None) -> TrustMetrics:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    feedback = db.query(OperatorFeedback).filter(
        OperatorFeedback.created_at >= since
    ).all()

    confirmed_useful = sum(1 for f in feedback if f.classification == "USEFUL")
    confirmed_fp = sum(1 for f in feedback if f.classification == "FALSE_POSITIVE")
    total_reviewed = len(feedback)

    finding_precision = None
    if (confirmed_useful + confirmed_fp) > 0:
        finding_precision = confirmed_useful / (confirmed_useful + confirmed_fp)

    approved_actionable = sum(1 for f in feedback if f.classification in ("USEFUL",))
    reviewed_actionable = sum(1 for f in feedback if f.classification not in ("UNKNOWN",))
    operator_acceptance = None
    if reviewed_actionable > 0:
        operator_acceptance = approved_actionable / reviewed_actionable

    scans = db.query(ScanJob).filter(ScanJob.created_at >= since).all()
    completed_attempts = [s for s in scans if s.status in ("completed", "failed")]
    successful = sum(1 for s in scans if s.status == "completed")
    scan_reliability = None
    if completed_attempts:
        scan_reliability = successful / len(completed_attempts)

    retry_scans = [s for s in scans if s.attempt and s.attempt > 1]
    retry_attempts = len(retry_scans)
    successful_retries = sum(1 for s in retry_scans if s.status == "completed")
    retry_recovery = None
    if retry_attempts > 0:
        retry_recovery = successful_retries / retry_attempts

    return TrustMetrics(
        finding_precision=finding_precision,
        operator_acceptance_rate=operator_acceptance,
        scan_reliability=scan_reliability,
        retry_recovery_rate=retry_recovery,
        safety_violation_count=0,
        journal_integrity_failure_count=0,
        confirmed_useful=confirmed_useful,
        confirmed_false_positives=confirmed_fp,
        total_reviewed=total_reviewed,
        approved_actionable=approved_actionable,
        reviewed_actionable=reviewed_actionable,
        successful_scans=successful,
        completed_scan_attempts=len(completed_attempts),
        successful_retries=successful_retries,
        retry_attempts=retry_attempts,
    )
