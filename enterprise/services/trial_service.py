"""Operational Trial lifecycle management."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models import OperationalTrial, DailySnapshot, Repository
from ..schemas import TrialCreate


def create_trial(db: Session, body: TrialCreate, operator: str) -> OperationalTrial:
    trial = OperationalTrial(
        trial_id=body.trial_id,
        started_at=datetime.now(timezone.utc),
        status="ACTIVE",
        operator=operator,
        repositories=body.repositories,
        baseline_version=body.baseline_version,
        baseline_commit=body.baseline_commit,
    )
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


def get_trial(db: Session, trial_id: str) -> OperationalTrial | None:
    return db.query(OperationalTrial).filter(OperationalTrial.trial_id == trial_id).first()


def get_active_trial(db: Session) -> OperationalTrial | None:
    return db.query(OperationalTrial).filter(OperationalTrial.status == "ACTIVE").first()


def complete_trial(db: Session, trial_id: str) -> OperationalTrial | None:
    trial = get_trial(db, trial_id)
    if not trial or trial.status != "ACTIVE":
        return None
    trial.status = "COMPLETED"
    trial.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(trial)
    return trial


def abort_trial(db: Session, trial_id: str) -> OperationalTrial | None:
    trial = get_trial(db, trial_id)
    if not trial or trial.status != "ACTIVE":
        return None
    trial.status = "ABORTED"
    trial.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(trial)
    return trial


def list_trials(db: Session, limit: int = 50) -> list[OperationalTrial]:
    return db.query(OperationalTrial).order_by(OperationalTrial.created_at.desc()).limit(limit).all()


def get_trial_repositories(db: Session, trial: OperationalTrial) -> list[Repository]:
    if not trial.repositories:
        return []
    return db.query(Repository).filter(Repository.id.in_(trial.repositories)).all()
