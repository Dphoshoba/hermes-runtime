"""Guided Mode router — non-technical operator experience API.

Translates the Evidence & Risk Gate into plain-language, decision-centered
workflows. Backend remains authoritative; this router only reshapes data
for Guided Mode consumption. No authority logic lives here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Finding, FindingAdjudication, Mission, PreparedChange, ProjectContext, Repository, User
from ..services import get_current_user

router = APIRouter()

# Plain-language label mapping (read-only presentation; not authority)
GATE_LABELS = {
    "INSUFFICIENT_EVIDENCE": "EVOSIA needs more context",
    "ACTIONABLE": "Worth addressing",
    "NOT_ACTIONABLE": "No action needed",
    "DUPLICATE": "Already covered",
    "POLICY_SUPPRESSED": "Excluded by policy",
}

MISSION_STATUS_LABELS = {
    "DRAFT": "Proposed work",
    "APPROVED_FOR_FUTURE_EXECUTION": "Approved for preparation",
    "PREPARED": "Prepared change",
    "BLOCKED": "Blocked",
    "DEFERRED": "Deferred",
    "NEEDS_REFINEMENT": "Needs refinement",
}

AUTHORITY_LEVEL_LABELS = {
    0: "Observe — EVOSIA inspects and explains",
    1: "Recommend — EVOSIA proposes work",
    2: "Prepare — EVOSIA creates changes in an isolated workspace",
}


class GuidedSummaryResponse(BaseModel):
    repository_id: str | None
    repository_name: str | None
    total_findings: int
    needs_attention: int
    needs_context: int
    proposed_work: int
    important_issue: int
    questions_awaiting_answer: int
    authority_level: int
    authority_level_label: str
    nothing_changed: bool
    headline: str
    status: str


class NeedsAttentionItem(BaseModel):
    finding_id: str
    title: str
    plain_title: str
    severity: str
    category: str
    why_it_matters: str
    current_classification: str | None
    classification_label: str | None
    has_human_decision: bool
    technical: dict[str, Any]


class ContextQuestion(BaseModel):
    question_id: str
    topic: str
    question: str
    why_asking: str
    affects_count: int
    affects_findings: list[str]
    scope: str
    options: list[str]
    technical: dict[str, Any]


class GuidedMission(BaseModel):
    mission_id: str
    title: str
    plain_title: str
    what: str
    why: str
    benefit: str
    risk: str
    scope: str
    validation: str
    rollback: str
    authority_consequence: str
    status: str
    status_label: str
    originating_finding: str
    human_adjudication_ref: str
    technical: dict[str, Any]


class ApprovePreparationRequest(BaseModel):
    operator: str = Field(min_length=1, max_length=255)


class ContextAddRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    scope: str = Field(default="project")
    source: str = Field(default="human_confirmed")
    actor: str = Field(min_length=1, max_length=255)


class QuestionAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)
    actor: str = Field(min_length=1, max_length=255)
    confidence: str = Field(default="human_confirmed")


def _human_classification(finding_id: str, db: Session) -> FindingAdjudication | None:
    return (
        db.query(FindingAdjudication)
        .filter(FindingAdjudication.finding_id == finding_id)
        .order_by(FindingAdjudication.reviewed_at.desc())
        .first()
    )


def _plain_title(finding: Finding) -> str:
    """Softer, non-alarming title variant for Guided Mode."""
    return finding.title or ""


def _why_it_matters(finding: Finding) -> str:
    """One-line plain-language why-it-matters derived from category."""
    cat = (finding.category or "").lower()
    title = (finding.title or "").lower()
    if "security" in cat or "credential" in title:
        return "This may involve sensitive information or access controls."
    if "debt" in cat:
        return "This may make future changes harder or error-prone."
    if "complexity" in cat:
        return "This part of the project may be harder to understand or change safely."
    if "coupling" in cat:
        return "This may create unexpected dependencies between parts of the project."
    if "depend" in cat:
        return "This may affect how reliably the project can be built or updated."
    if "test" in cat:
        return "This may reduce confidence that changes work as expected."
    if "config" in cat or "configuration" in cat:
        return "This may affect how the project is set up or deployed."
    if "public api" in cat or "api" in title:
        return "This may affect how other parts of the project interact with this area."
    return "EVOSIA observed something worth your awareness."


def _build_headline(total: int, attn: int, ctx: int, important: int, proposed: int) -> str:
    parts = [f"I reviewed your project.", f"{total} things examined"]
    if attn:
        parts.append(f"{attn} worth discussing")
    if ctx:
        parts.append(f"{ctx} questions need your help")
    if important:
        parts.append(f"{important} important issue")
    if proposed:
        parts.append(f"{proposed} proposed change")
    parts.append("0 changes made")
    return " · ".join(parts)


@router.get("/summary", response_model=GuidedSummaryResponse)
def guided_summary(
    repository_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    q = db.query(Finding)
    if repository_id:
        q = q.filter(Finding.repository_id == repository_id)
    findings = q.all()

    needs_attention = 0
    needs_context = 0
    important_issue = 0
    for f in findings:
        adj = _human_classification(f.id, db)
        if adj is None:
            if (f.severity or "").lower() in ("critical", "high"):
                important_issue += 1
            needs_context += 1
        elif adj.classification == "ACTIONABLE":
            needs_attention += 1

    mission_q = db.query(Mission)
    if repository_id:
        mission_q = mission_q.filter(Mission.repository_id == repository_id)
    proposed_work = mission_q.filter(
        Mission.status.in_(["DRAFT", "APPROVED_FOR_FUTURE_EXECUTION", "NEEDS_REFINEMENT"])
    ).count()

    repo_name = None
    if repository_id:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        repo_name = repo.name if repo else None

    total = len(findings)
    headline = _build_headline(total, needs_attention, needs_context, important_issue, proposed_work)

    return {
        "repository_id": repository_id,
        "repository_name": repo_name,
        "total_findings": total,
        "needs_attention": needs_attention,
        "needs_context": needs_context,
        "proposed_work": proposed_work,
        "important_issue": important_issue,
        "questions_awaiting_answer": needs_context,
        "authority_level": 1,
        "authority_level_label": AUTHORITY_LEVEL_LABELS[1],
        "nothing_changed": True,
        "headline": headline,
        "status": "scan_complete",
        "permissions": {
            "can_observe": True,
            "can_recommend": True,
            "can_prepare": False,
            "can_propose": False,
            "can_execute": False,
            "execution_enabled": False,
            "mutation_enabled": False,
        },
    }


@router.get("/needs-attention", response_model=list[NeedsAttentionItem])
def needs_attention(
    repository_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    q = db.query(Finding)
    if repository_id:
        q = q.filter(Finding.repository_id == repository_id)
    items = []
    for f in q.all():
        adj = _human_classification(f.id, db)
        if adj is None or adj.classification != "ACTIONABLE":
            continue
        items.append({
            "finding_id": f.id,
            "title": f.title,
            "plain_title": _plain_title(f),
            "severity": f.severity,
            "category": f.category,
            "why_it_matters": _why_it_matters(f),
            "current_classification": adj.classification,
            "classification_label": GATE_LABELS.get(adj.classification, adj.classification),
            "has_human_decision": True,
            "technical": {
                "module": f.module,
                "evidence_references": (f.metadata_json or {}).get("evidence_references", []),
                "gate_state": f.gate_state,
                "adjudication_id": adj.id,
            },
        })
    return items


def _cluster_topic(f: Finding) -> str:
    cat = (f.category or "").lower()
    title = (f.title or "").lower()
    if "isolated" in title or "isolated" in cat:
        return "Intentionally separate modules"
    if "large" in title and ("module" in title or "component" in title or "api" in title):
        return "Large or complex areas"
    if "hook" in title or "api" in title or "concentration" in title:
        return "Concentrated responsibilities"
    if "depend" in cat:
        return "Dependency choices"
    if "config" in cat or "configuration" in cat:
        return "Configuration setup"
    if "security" in cat or "credential" in title:
        return "Security-sensitive code"
    return "Other observations"


def _question_for_topic(topic: str) -> str:
    questions = {
        "Intentionally separate modules": (
            "I found several modules that appear deliberately separate. "
            "Are these intentionally isolated because they perform independent jobs?"
        ),
        "Large or complex areas": (
            "I found some modules that look large or complex. "
            "Are these intentionally built this way, or would you prefer they be simpler?"
        ),
        "Concentrated responsibilities": (
            "I found areas where many responsibilities seem concentrated. "
            "Is this intentional design, or could it be simplified?"
        ),
        "Dependency choices": (
            "I found some dependency choices that may affect reliability. "
            "Are these versions intentionally left flexible?"
        ),
        "Configuration setup": (
            "I found some configuration items that may be missing. "
            "Are these intentionally omitted or could they be needed?"
        ),
        "Security-sensitive code": (
            "I found code that may involve sensitive access. "
            "Is this an area where extra caution is intended?"
        ),
        "Other observations": "I found some observations about the project. Would you like to provide context on these?",
    }
    return questions.get(topic, "I found some observations. Can you provide context?")


def _why_ask_for_topic(topic: str) -> str:
    reasons = {
        "Intentionally separate modules": (
            "This helps EVOSIA understand whether separation is deliberate, "
            "so it doesn't suggest unnecessary changes."
        ),
        "Large or complex areas": "This helps EVOSIA know whether complexity is intentional or a sign of a problem.",
        "Concentrated responsibilities": "This helps EVOSIA judge whether a refactor is wanted or the design is intentional.",
        "Dependency choices": "This helps EVOSIA judge whether unpinned dependencies are a risk or an accepted trade-off.",
        "Configuration setup": "This helps EVOSIA judge whether missing configuration is a real gap or intentional.",
        "Security-sensitive code": "This helps EVOSIA treat security-relevant code with appropriate caution.",
        "Other observations": "Your context helps EVOSIA reduce unnecessary findings.",
    }
    return reasons.get(topic, "Your context helps EVOSIA reduce unnecessary findings.")


@router.get("/needs-context", response_model=list[ContextQuestion])
def needs_context(
    repository_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    q = db.query(Finding)
    if repository_id:
        q = q.filter(Finding.repository_id == repository_id)
    nme_by_topic: dict[str, list[Finding]] = {}
    for f in q.all():
        adj = _human_classification(f.id, db)
        if adj is not None:
            continue
        topic = _cluster_topic(f)
        nme_by_topic.setdefault(topic, []).append(f)

    questions = []
    for topic, findings in nme_by_topic.items():
        questions.append({
            "question_id": f"ctx-{topic.lower().replace(' ', '-')}",
            "topic": topic,
            "question": _question_for_topic(topic),
            "why_asking": _why_ask_for_topic(topic),
            "affects_count": len(findings),
            "affects_findings": [f.id for f in findings],
            "scope": "project",
            "options": ["Yes", "No", "I don't know", "Ask someone else / later"],
            "technical": {
                "finding_ids": [f.id for f in findings],
                "categories": list(set(f.category for f in findings)),
                "severities": list(set(f.severity for f in findings)),
            },
        })
    return questions


@router.get("/missions", response_model=list[GuidedMission])
def guided_missions(
    repository_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    q = db.query(Mission)
    if repository_id:
        q = q.filter(Mission.repository_id == repository_id)
    missions = q.order_by(Mission.created_at.desc()).all()
    out = []
    for m in missions:
        meta = m.metadata_json or {}
        out.append({
            "mission_id": m.id,
            "title": m.title,
            "plain_title": m.title,
            "what": m.description or "Proposed engineering work.",
            "why": "Based on a human-ACTIONABLE finding.",
            "benefit": "Addresses an operator-flagged engineering concern.",
            "risk": "Change risk depends on scope; prepared changes remain unreviewed until you act.",
            "scope": meta.get("scope", "To be determined during preparation."),
            "validation": "Tests and checks would run before any change is finalized.",
            "rollback": "Prepared changes are isolated and reversible until merged/deployed.",
            "authority_consequence": (
                "Approving here permits EVOSIA to PREPARE a proposed change "
                "in an isolated workspace. It will NOT merge, deploy, or change production."
            ),
            "status": m.status,
            "status_label": MISSION_STATUS_LABELS.get(m.status, m.status),
            "originating_finding": meta.get("originating_finding_id", ""),
            "human_adjudication_ref": meta.get("governance_approval_reference", ""),
            "technical": {
                "mission_type": m.mission_type,
                "priority": m.priority,
                "repository_id": m.repository_id,
            },
        })
    return out


@router.post("/missions/{mission_id}/approve-preparation")
def approve_preparation(
    mission_id: str,
    body: ApprovePreparationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status not in ("DRAFT", "NEEDS_REFINEMENT"):
        raise HTTPException(status_code=409, detail="Mission is not in an approvable state")
    mission.status = "APPROVED_FOR_FUTURE_EXECUTION"
    mission.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "mission_id": mission.id,
        "status": mission.status,
        "status_label": MISSION_STATUS_LABELS[mission.status],
        "execution_authorized": False,
        "message": (
            "Approved for preparation. EVOSIA may prepare the change in an "
            "isolated workspace. Nothing has been executed or deployed."
        ),
    }


@router.get("/permission")
def permission_level(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "level": 1,
        "label": AUTHORITY_LEVEL_LABELS[1],
        "can_observe": True,
        "can_recommend": True,
        "can_prepare": False,
        "can_propose": False,
        "can_execute": False,
        "execution_enabled": False,
        "mutation_enabled": False,
    }


# ---------------------------------------------------------------------------
# M2 — Project Context Engine
# ---------------------------------------------------------------------------

class ContextItemRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1)
    scope: str = Field(default="project")
    confidence: str = Field(default="human_confirmed")


class ContextItemResponse(BaseModel):
    id: str
    topic: str
    key: str
    value: str
    source: str
    actor: str
    scope: str
    confidence: str
    is_current: bool
    created_at: str


@router.get("/context", response_model=None)
def list_context(
    repository_id: str | None = None,
    topic: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    q = db.query(ProjectContext).filter(ProjectContext.is_current == True)
    if repository_id:
        q = q.filter(ProjectContext.repository_id == repository_id)
    if topic:
        q = q.filter(ProjectContext.topic == topic)
    items = q.order_by(ProjectContext.topic, ProjectContext.key).all()
    return [
        {
            "id": c.id,
            "topic": c.topic,
            "key": c.key,
            "value": c.value,
            "source": c.source,
            "actor": c.actor,
            "scope": c.scope,
            "confidence": c.confidence,
            "is_current": c.is_current,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in items
    ]


@router.post("/context", response_model=ContextItemResponse)
def add_context(
    body: ContextItemRequest,
    repository_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectContext:
    item = ProjectContext(
        repository_id=repository_id,
        topic=body.topic,
        key=body.key,
        value=body.value,
        source="human_confirmed",
        actor=user.name,
        scope=body.scope,
        confidence=body.confidence,
        is_current=True,
        provenance={"origin": "guided_mode", "user_id": user.id},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/context/{context_id}")
def delete_context(
    context_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    item = db.query(ProjectContext).filter(ProjectContext.id == context_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Context item not found")
    item.is_current = False
    db.commit()
    return {"status": "removed", "id": context_id}


# ---------------------------------------------------------------------------
# M6 — Prepared Change Sandbox
# ---------------------------------------------------------------------------

@router.post("/missions/{mission_id}/prepare")
def prepare_change(
    mission_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status != "APPROVED_FOR_FUTURE_EXECUTION":
        raise HTTPException(status_code=409, detail="Mission must be approved for preparation first")

    prepared = PreparedChange(
        mission_id=mission.id,
        repository_id=mission.repository_id,
        title=mission.title,
        description=mission.description,
        status="preparing",
        affected_files=[],
        validation_status="pending",
        created_by=user.name,
        provenance={
            "origin": "guided_mode",
            "mission_id": mission.id,
            "user_id": user.id,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    mission.status = "PREPARED"
    mission.updated_at = datetime.now(timezone.utc)
    db.add(prepared)
    db.commit()
    db.refresh(prepared)

    return {
        "prepared_change_id": prepared.id,
        "mission_id": mission.id,
        "status": prepared.status,
        "workspace_path": prepared.workspace_path,
        "affected_files": prepared.affected_files,
        "validation_status": prepared.validation_status,
        "message": "Change is being prepared in an isolated workspace. Nothing has been executed or deployed.",
        "execution_authorized": False,
    }


@router.get("/prepared-changes", response_model=None)
def list_prepared_changes(
    repository_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    q = db.query(PreparedChange)
    if repository_id:
        q = q.filter(PreparedChange.repository_id == repository_id)
    items = q.order_by(PreparedChange.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "mission_id": p.mission_id,
            "title": p.title,
            "status": p.status,
            "affected_files": p.affected_files,
            "validation_status": p.validation_status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in items
    ]


@router.get("/prepared-changes/{prepared_id}")
def get_prepared_change(
    prepared_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    prepared = db.query(PreparedChange).filter(PreparedChange.id == prepared_id).first()
    if not prepared:
        raise HTTPException(status_code=404, detail="Prepared change not found")
    return {
        "id": prepared.id,
        "mission_id": prepared.mission_id,
        "repository_id": prepared.repository_id,
        "title": prepared.title,
        "description": prepared.description,
        "status": prepared.status,
        "workspace_path": prepared.workspace_path,
        "affected_files": prepared.affected_files,
        "validation_status": prepared.validation_status,
        "validation_output": prepared.validation_output,
        "created_by": prepared.created_by,
        "created_at": prepared.created_at.isoformat() if prepared.created_at else None,
    }
