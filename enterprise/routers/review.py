"""Review router — Human Review Queue + Adjudication API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FindingAdjudication, User
from ..schemas import FindingResponse
from ..services import get_current_user
from ..services.review_service import (
    build_review_queue,
    create_adjudication,
    get_adjudications_for_finding,
    get_review_summary,
    get_pending_count,
    emit_finding_reviewed,
    emit_finding_reclassified,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AdjudicationCreate(BaseModel):
    classification: str = Field(
        pattern=r"^(USEFUL|FALSE_POSITIVE|NOT_ACTIONABLE|NEEDS_MORE_EVIDENCE|DUPLICATE|UNKNOWN)$"
    )
    notes: str | None = None
    operator: str = Field(min_length=1, max_length=255)
    trial_id: str | None = None


class AdjudicationResponse(BaseModel):
    id: str
    finding_id: str
    repository_id: str | None
    classification: str
    observation_status: str
    concern_status: str
    actionability_status: str
    file_context: str
    exceedance_ratio: float | None
    operator: str
    operator_notes: str | None
    reviewed_at: datetime
    source: str
    confidence: float
    governance_decision_at_review: str | None
    related_mission_ids: list[str]
    schema_version: str

    class Config:
        from_attributes = True


class ReviewQueueItem(BaseModel):
    finding_id: str
    db_id: str
    scan_id: str | None
    commit_sha: str | None
    repository_id: str | None
    repository_name: str
    severity: str
    category: str
    title: str
    description: str
    module: str
    file_context: str
    line_count: int | None
    exceedance_ratio: float | None
    exceedance_tier: str | None
    evidence_references: list[dict[str, Any]]
    governance_decision: str
    governance_rationale: str
    observation_status: str
    concern_status: str
    actionability_status: str
    mission_linkage: list[str] | str
    current_adjudication: str | None
    operator: str | None
    operator_notes: str | None
    reviewed_at: str | None


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    limit: int
    offset: int


class ReviewSummaryResponse(BaseModel):
    total_reviewed: int
    useful: int
    false_positive: int
    not_actionable: int
    needs_more_evidence: int
    duplicate: int
    unknown: int
    finding_precision: float | None
    actionability_rate: float | None
    pending_review: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/findings", response_model=ReviewQueueResponse)
def list_review_findings(
    repository_id: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    reviewed: bool | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    result = build_review_queue(
        db,
        repository_id=repository_id,
        severity=severity,
        category=category,
        reviewed=reviewed,
        limit=limit,
        offset=offset,
    )
    result["pending_review"] = get_pending_count(db)
    return result


@router.get("/findings/{finding_id}", response_model=dict)
def get_review_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    from ..models import Finding, Repository
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    repo = db.query(Repository).filter(Repository.id == finding.repository_id).first()
    adjudications = get_adjudications_for_finding(db, finding_id)
    from ..services.review_service import (
        classify_file_context, infer_observation_status, infer_concern_status,
        infer_actionability_status, _extract_line_count, compute_exceedance_ratio,
        classify_exceedance_tier,
    )
    file_context = classify_file_context(finding.module or "")
    line_count = _extract_line_count(finding)
    exceedance = compute_exceedance_ratio(line_count, 300) if line_count else None

    from ..models import ScanJob
    scan = (
        db.query(ScanJob)
        .filter(
            ScanJob.repository_id == finding.repository_id,
            ScanJob.status == "completed",
        )
        .order_by(ScanJob.completed_at.desc())
        .first()
    )

    return {
        "finding": {
            "id": finding.id,
            "scan_id": scan.id if scan else None,
            "commit_sha": scan.commit_sha if scan else None,
            "repository_id": finding.repository_id,
            "repository_name": repo.name if repo else "UNKNOWN",
            "severity": finding.severity,
            "category": finding.category,
            "title": finding.title,
            "description": finding.description or "",
            "module": finding.module or "",
            "file_context": file_context,
            "line_count": line_count,
            "exceedance_ratio": exceedance,
            "exceedance_tier": classify_exceedance_tier(exceedance) if exceedance else None,
            "evidence_references": (finding.metadata_json or {}).get("evidence_references", []),
            "governance_decision": (finding.metadata_json or {}).get("governance_decision", {}).get("decision", "N/A"),
            "governance_rationale": (finding.metadata_json or {}).get("governance_decision", {}).get("rationale", ""),
            "observation_status": infer_observation_status(finding),
            "concern_status": infer_concern_status(finding, file_context),
            "actionability_status": infer_actionability_status(finding, file_context, exceedance),
        },
        "adjudications": [
            {
                "id": a.id,
                "classification": a.classification,
                "observation_status": a.observation_status,
                "concern_status": a.concern_status,
                "actionability_status": a.actionability_status,
                "file_context": a.file_context,
                "operator": a.operator,
                "operator_notes": a.operator_notes,
                "reviewed_at": a.reviewed_at.isoformat(),
            }
            for a in adjudications
        ],
    }


@router.post("/findings/{finding_id}/adjudications", response_model=AdjudicationResponse)
def create_finding_adjudication(
    finding_id: str,
    body: AdjudicationCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> FindingAdjudication:
    from ..models import Finding
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    existing = get_adjudications_for_finding(db, finding_id)
    adjudication = create_adjudication(
        db,
        finding_id=finding_id,
        classification=body.classification,
        operator=body.operator,
        notes=body.notes,
        trial_id=body.trial_id,
    )

    if existing:
        emit_finding_reclassified(
            db,
            finding_id=finding_id,
            repository_id=finding.repository_id,
            classification=body.classification,
            operator=body.operator,
            previous_adjudication_id=existing[0].id,
            notes=body.notes,
            adjudication_id=adjudication.id,
            trial_id=body.trial_id,
        )
    else:
        emit_finding_reviewed(
            db,
            finding_id=finding_id,
            repository_id=finding.repository_id,
            classification=body.classification,
            operator=body.operator,
            notes=body.notes,
            adjudication_id=adjudication.id,
            trial_id=body.trial_id,
        )

    return adjudication


@router.get("/summary", response_model=ReviewSummaryResponse)
def review_summary(
    trial_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    summary = get_review_summary(db, trial_id=trial_id)
    summary["pending_review"] = get_pending_count(db)
    return summary


@router.get("/export")
def export_review_data(
    trial_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    queue = build_review_queue(db, limit=1000)
    summary = get_review_summary(db, trial_id=trial_id)
    return {
        "summary": summary,
        "queue": queue,
    }
