"""Findings router — query engineering findings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Finding, User
from ..schemas import FindingResponse
from ..services import get_current_user

router = APIRouter()


@router.get("", response_model=list[FindingResponse])
def list_findings(
    repository_id: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Finding]:
    q = db.query(Finding)
    if repository_id:
        q = q.filter(Finding.repository_id == repository_id)
    if severity:
        q = q.filter(Finding.severity == severity)
    if category:
        q = q.filter(Finding.category == category)
    if status:
        q = q.filter(Finding.status == status)
    return q.order_by(Finding.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    from fastapi import HTTPException
    from ..models import FindingAdjudication

    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Evidence & Risk Gate authority enrichment (Post Cycle 8).
    # Source the human / suppression authority from the adjudication table so
    # clients can clearly distinguish machine gate vs human vs legacy vs policy.
    adjudications = (
        db.query(FindingAdjudication)
        .filter(FindingAdjudication.finding_id == finding_id)
        .order_by(FindingAdjudication.reviewed_at.asc())
        .all()
    )
    supp = next((a for a in adjudications if getattr(a, "policy_suppressed", False)), None)
    latest = adjudications[-1] if adjudications else None

    enriched = {
        "id": finding.id,
        "repository_id": finding.repository_id,
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "category": finding.category,
        "title": finding.title,
        "description": finding.description,
        "module": finding.module,
        "priority_score": finding.priority_score,
        "effort": finding.effort,
        "status": finding.status,
        "created_at": finding.created_at,
        "gate_state": finding.gate_state,
        "risk_band": finding.risk_band,
        "review_rank": finding.review_rank,
        "legacy_decision": finding.legacy_decision,
        "policy_suppressed": bool(supp.policy_suppressed) if supp else False,
        "suppression_rule_id": supp.suppression_rule_id if supp else None,
        "suppression_rule_version": supp.suppression_rule_version if supp else None,
        "human_classification": latest.classification if latest else None,
        "human_operator": latest.operator if latest else None,
        # Mission eligibility tracks the CURRENT effective human classification
        # (append-only history is preserved; reclassification to NOT_ACTIONABLE
        # flips eligibility off).
        "mission_eligible": (latest is not None and latest.classification == "ACTIONABLE"),
    }
    return enriched
