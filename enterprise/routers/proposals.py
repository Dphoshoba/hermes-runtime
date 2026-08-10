"""Feature Proposal router — evidence-based feature acceptance policy."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, FeatureProposal
from ..schemas import FeatureProposalCreate, FeatureProposalResponse, FeatureDecision
from ..services import get_current_user
from ..services.trial_service import get_active_trial

router = APIRouter()


@router.post("", response_model=FeatureProposalResponse, status_code=201)
def propose_feature(
    body: FeatureProposalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeatureProposalResponse:
    trial = get_active_trial(db)
    if not trial:
        raise HTTPException(status_code=400, detail="No active trial")
    proposal = FeatureProposal(
        trial_id=trial.trial_id,
        problem=body.problem,
        observed_evidence=body.observed_evidence,
        frequency=body.frequency,
        affected_repositories=body.affected_repositories,
        current_workaround=body.current_workaround,
        risk=body.risk,
        expected_benefit=body.expected_benefit,
        success_metric=body.success_metric,
        implementation_estimate=body.implementation_estimate,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("", response_model=list[FeatureProposalResponse])
def list_proposals(
    trial_id: str | None = None,
    decision: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FeatureProposalResponse]:
    q = db.query(FeatureProposal)
    if trial_id:
        q = q.filter(FeatureProposal.trial_id == trial_id)
    if decision:
        q = q.filter(FeatureProposal.decision == decision)
    return q.order_by(FeatureProposal.created_at.desc()).limit(limit).all()


@router.post("/{proposal_id}/decide", response_model=FeatureProposalResponse)
def decide_feature(
    proposal_id: str,
    body: FeatureDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeatureProposalResponse:
    proposal = db.query(FeatureProposal).filter(FeatureProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal.decision = body.decision
    proposal.decision_notes = body.decision_notes
    proposal.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)
    return proposal
