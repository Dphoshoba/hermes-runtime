"""Final 7-Day Report Generator — OPERATIONAL_VALIDATION_REPORT.md."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models import (
    OperationalTrial, DailySnapshot, OperatorFeedback, FrictionRecord,
    FeatureProposal, ScanJob, Finding, Repository,
)
from .trust_service import calculate_trust_metrics
from .metrics_service import collect_daily_metrics


def generate_final_report(db: Session, trial_id: str) -> str:
    trial = db.query(OperationalTrial).filter(OperationalTrial.trial_id == trial_id).first()
    if not trial:
        return "# Trial not found"

    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.trial_id == trial_id
    ).order_by(DailySnapshot.date).all()

    trust = calculate_trust_metrics(db)
    feedback = db.query(OperatorFeedback).filter(
        OperatorFeedback.trial_id == trial_id
    ).all()
    friction = db.query(FrictionRecord).filter(
        FrictionRecord.trial_id == trial_id
    ).all()
    proposals = db.query(FeatureProposal).filter(
        FeatureProposal.trial_id == trial_id
    ).all()

    repos = db.query(Repository).filter(
        Repository.id.in_(trial.repositories or [])
    ).all() if trial.repositories else []

    lines = [
        f"# OPERATIONAL VALIDATION REPORT",
        f"",
        f"**Milestone:** 7-Day Operational Validation Program v1.0",
        f"**Trial ID:** {trial.trial_id}",
        f"**Status:** {trial.status}",
        f"**Operator:** {trial.operator}",
        f"**Started:** {trial.started_at}",
        f"**Completed:** {trial.completed_at or 'In Progress'}",
        f"**Days:** {len(snapshots)}",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"This report summarizes {len(snapshots)} days of operational validation.",
        f"",
        f"---",
        f"",
        f"## Repository Cohort",
        f"",
    ]

    for r in repos:
        lines.append(f"- **{r.name}** ({r.language or 'unknown'}) — {r.url}")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Scan Reliability",
        f"",
        f"- Successful scans: {trust.successful_scans}",
        f"- Completed attempts: {trust.completed_scan_attempts}",
        f"- Scan reliability: {trust.scan_reliability:.1%}" if trust.scan_reliability else "- Scan reliability: N/A",
        f"- Retry recovery rate: {trust.retry_recovery_rate:.1%}" if trust.retry_recovery_rate else "- Retry recovery rate: N/A",
        f"",
        f"---",
        f"",
        f"## Finding Quality",
        f"",
        f"- Total reviewed: {trust.total_reviewed}",
        f"- Confirmed useful: {trust.confirmed_useful}",
        f"- Confirmed false positives: {trust.confirmed_false_positives}",
        f"- Finding precision: {trust.finding_precision:.1%}" if trust.finding_precision else "- Finding precision: N/A",
        f"",
        f"---",
        f"",
        f"## False Positive Analysis",
        f"",
    ])

    fp_feedback = [f for f in feedback if f.classification == "FALSE_POSITIVE"]
    if fp_feedback:
        for f in fp_feedback:
            lines.append(f"- Finding {f.finding_id}: {f.notes or 'No notes'}")
    else:
        lines.append("- No false positives confirmed")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Governance Quality",
        f"",
        f"- Operator acceptance rate: {trust.operator_acceptance_rate:.1%}" if trust.operator_acceptance_rate else "- Operator acceptance rate: N/A",
        f"",
        f"---",
        f"",
        f"## Operator Feedback",
        f"",
    ])

    if feedback:
        by_class: dict[str, int] = {}
        for f in feedback:
            by_class[f.classification] = by_class.get(f.classification, 0) + 1
        for cls, count in sorted(by_class.items()):
            lines.append(f"- {cls}: {count}")
    else:
        lines.append("- No feedback recorded")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Operational Friction",
        f"",
    ])

    if friction:
        by_cat: dict[str, int] = {}
        for f in friction:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
        for cat, count in sorted(by_cat.items()):
            lines.append(f"- {cat}: {count}")
    else:
        lines.append("- No friction recorded")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Safety Results",
        f"",
        f"- Safety violations: {trust.safety_violation_count}",
        f"- Journal integrity failures: {trust.journal_integrity_failure_count}",
        f"",
        f"---",
        f"",
        f"## Daily Trends",
        f"",
    ])

    for snap in snapshots:
        m = snap.metrics or {}
        lines.append(
            f"| {snap.date} | {m.get('successful_scans', 0)} scans | "
            f"{m.get('findings_generated', 0)} findings | "
            f"{m.get('useful_findings_confirmed', 0)} useful | "
            f"{m.get('false_positives_confirmed', 0)} FP |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Feature Proposals",
        f"",
    ])

    if proposals:
        for p in proposals:
            lines.extend([
                f"### {p.decision}",
                f"- **Problem:** {p.problem}",
                f"- **Evidence:** {p.observed_evidence}",
                f"- **Frequency:** {p.frequency or 'Unknown'}",
                f"- **Decision:** {p.decision}",
                f"",
            ])
    else:
        lines.append("- No feature proposals recorded")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Recommended Bug Fixes",
        f"",
        f"(To be populated from trial data)",
        f"",
        f"---",
        f"",
        f"## Candidate Future Features",
        f"",
        f"(Requires evidence-based feature acceptance policy)",
        f"",
        f"---",
        f"",
        f"*Report generated at {datetime.now(timezone.utc).isoformat()}*",
    ])

    return "\n".join(lines)
