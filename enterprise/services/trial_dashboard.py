"""7-Day Trial Dashboard — aggregated trial view."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import OperationalTrial, DailySnapshot
from ..schemas import TrialDashboard, TrialDaySummary


def get_trial_dashboard(db: Session, trial_id: str) -> TrialDashboard | None:
    trial = db.query(OperationalTrial).filter(OperationalTrial.trial_id == trial_id).first()
    if not trial:
        return None

    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.trial_id == trial_id
    ).order_by(DailySnapshot.date).all()

    daily_summaries = []
    cumulative = {
        "scans": 0, "findings": 0, "useful": 0, "false_positive": 0,
        "governance": 0, "missions": 0, "failures": 0, "friction": 0,
    }

    for i, snap in enumerate(snapshots, 1):
        m = snap.metrics or {}
        daily = TrialDaySummary(
            day_number=i,
            date=snap.date,
            scans=m.get("successful_scans", 0) + m.get("failed_scans", 0),
            reliability=None,
            findings=m.get("findings_generated", 0),
            useful=m.get("useful_findings_confirmed", 0),
            false_positive=m.get("false_positives_confirmed", 0),
            governance=m.get("governance_approved", 0) + m.get("governance_rejected", 0),
            missions=m.get("missions_generated", 0),
            failures=m.get("failed_scans", 0),
            friction=0,
        )
        total_scans = daily.scans
        if total_scans > 0:
            daily.reliability = m.get("successful_scans", 0) / total_scans

        cumulative["scans"] += daily.scans
        cumulative["findings"] += daily.findings
        cumulative["useful"] += daily.useful
        cumulative["false_positive"] += daily.false_positive
        cumulative["governance"] += daily.governance
        cumulative["missions"] += daily.missions
        cumulative["failures"] += daily.failures
        cumulative["friction"] += daily.friction
        daily_summaries.append(daily)

    return TrialDashboard(
        trial_id=trial.trial_id,
        status=trial.status,
        started_at=trial.started_at.isoformat() if trial.started_at else "",
        days_completed=len(snapshots),
        daily_summaries=daily_summaries,
        cumulative=cumulative,
    )
