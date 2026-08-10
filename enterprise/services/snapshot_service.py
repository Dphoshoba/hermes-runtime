"""Daily Snapshot — immutable end-of-day records."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models import DailySnapshot, OperationalTrial
from ..schemas import DailySnapshotResponse
from .metrics_service import collect_daily_metrics
from .trust_service import calculate_trust_metrics


def create_daily_snapshot(db: Session, trial_id: str, date_str: str) -> DailySnapshot:
    trial = db.query(OperationalTrial).filter(OperationalTrial.trial_id == trial_id).first()
    metrics = collect_daily_metrics(db, date_str)
    trust = calculate_trust_metrics(db)

    snapshot = DailySnapshot(
        trial_id=trial_id,
        date=date_str,
        hermes_version=trial.baseline_version if trial else None,
        hermes_commit=trial.baseline_commit if trial else None,
        repositories=trial.repositories if trial else [],
        metrics=metrics.model_dump(),
        operator_feedback=[],
        friction=[],
        failures=[],
        safety_incidents=[],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_snapshot(db: Session, trial_id: str, date_str: str) -> DailySnapshot | None:
    return db.query(DailySnapshot).filter(
        DailySnapshot.trial_id == trial_id,
        DailySnapshot.date == date_str,
    ).first()


def list_snapshots(db: Session, trial_id: str) -> list[DailySnapshot]:
    return db.query(DailySnapshot).filter(
        DailySnapshot.trial_id == trial_id
    ).order_by(DailySnapshot.date).all()
