"""Operational Trial router — lifecycle, snapshots, dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    TrialCreate, TrialResponse, DailySnapshotResponse,
    TrialDashboard,
)
from ..services import get_current_user
from ..services.trial_service import (
    create_trial, get_trial, complete_trial, abort_trial, list_trials,
)
from ..services.snapshot_service import (
    create_daily_snapshot, get_snapshot, list_snapshots,
)
from ..services.trial_dashboard import get_trial_dashboard

router = APIRouter()


@router.post("", response_model=TrialResponse, status_code=201)
def start_trial(
    body: TrialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrialResponse:
    trial = create_trial(db, body, user.email)
    return trial


@router.get("", response_model=list[TrialResponse])
def list_all_trials(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TrialResponse]:
    return list_trials(db, limit)


@router.get("/{trial_id}", response_model=TrialResponse)
def get_trial_detail(
    trial_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrialResponse:
    trial = get_trial(db, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial


@router.post("/{trial_id}/complete", response_model=TrialResponse)
def complete_trial_endpoint(
    trial_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrialResponse:
    trial = complete_trial(db, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Active trial not found")
    return trial


@router.post("/{trial_id}/abort", response_model=TrialResponse)
def abort_trial_endpoint(
    trial_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrialResponse:
    trial = abort_trial(db, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Active trial not found")
    return trial


@router.post("/{trial_id}/snapshots/{date}", response_model=DailySnapshotResponse, status_code=201)
def create_snapshot(
    trial_id: str,
    date: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailySnapshotResponse:
    snapshot = create_daily_snapshot(db, trial_id, date)
    return snapshot


@router.get("/{trial_id}/snapshots", response_model=list[DailySnapshotResponse])
def list_trial_snapshots(
    trial_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DailySnapshotResponse]:
    return list_snapshots(db, trial_id)


@router.get("/{trial_id}/dashboard", response_model=TrialDashboard)
def trial_dashboard(
    trial_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrialDashboard:
    dashboard = get_trial_dashboard(db, trial_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Trial not found")
    return dashboard
