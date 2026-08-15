"""Scanner Service — background scan execution for repositories.

Uses the Enterprise-Core bridge to invoke real EVOSIA Core pipeline stages.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import ScanJob, ScanHistory, Repository, Finding, JournalEvent

logger = logging.getLogger(__name__)

SCAN_STAGES = [
    "metadata",
    "materialization",
    "readiness",
    "repository_intelligence",
    "engineering_intelligence",
    "governance",
    "mission_recommendation",
    "persistence",
    "journal",
]

CANCELABLE_STATUSES = {"pending", "queued", "running"}
RETRYABLE_STATUSES = {"failed", "cancelled"}


def create_scan_job(
    db: Session,
    repository_id: str,
    scan_type: str = "full",
    branch: str | None = None,
    requested_by: str | None = None,
    previous_scan_id: str | None = None,
    attempt: int = 1,
) -> ScanJob:
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise ValueError(f"Repository {repository_id} not found")
    job = ScanJob(
        repository_id=repository_id,
        scan_type=scan_type,
        branch=branch or repo.default_branch,
        status="pending",
        requested_by=requested_by,
        previous_scan_id=previous_scan_id,
        attempt=attempt,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def start_scan(db: Session, job_id: str) -> ScanJob:
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise ValueError(f"Scan job {job_id} not found")
    if job.status not in ("pending", "queued"):
        raise ValueError(f"Scan job {job_id} is in status {job.status}, cannot start")

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    materialized_path = None
    try:
        _run_scan(db, job)
        if job.status == "cancelled":
            return job
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = _elapsed_seconds(job.started_at, job.completed_at)
        _add_history(db, job, "completed", "completed")
        _emit_journal_event(db, job, "scan.completed", {
            "scan_id": job.id,
            "repository_id": job.repository_id,
            "attempt": job.attempt,
            "duration_seconds": job.duration_seconds,
            "stages_completed": job.stages_completed or [],
        })
    except Exception as e:
        if job.status == "cancelled":
            return job
        job.status = "failed"
        job.error_message = str(e)[:2000]
        job.failure_classification = _classify_error(e)
        job.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = _elapsed_seconds(job.started_at, job.completed_at)
        _add_history(db, job, "failed", "failed", str(e)[:2000])
        _emit_journal_event(db, job, "scan.failed", {
            "scan_id": job.id,
            "repository_id": job.repository_id,
            "attempt": job.attempt,
            "error": str(e)[:500],
            "failure_classification": job.failure_classification,
        })
        logger.exception("Scan job %s failed", job_id)

    db.commit()
    db.refresh(job)
    return job


def cancel_scan(db: Session, job_id: str, requested_by: str | None = None) -> ScanJob:
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise ValueError(f"Scan job {job_id} not found")
    if job.status in ("completed", "failed", "cancelled"):
        return job
    now = datetime.now(timezone.utc)
    job.cancellation_requested_at = now
    job.status = "cancelled"
    job.cancelled_at = now
    job.completed_at = now
    job.duration_seconds = _elapsed_seconds(job.started_at, now)
    job.error_message = job.error_message or "Cancelled by user"
    if requested_by:
        job.requested_by = requested_by
    _add_history(db, job, "cancelled", "cancelled", "Scan cancelled by user")
    _emit_journal_event(db, job, "scan.cancelled", {
        "scan_id": job.id,
        "repository_id": job.repository_id,
        "requested_by": requested_by,
    })
    db.commit()
    db.refresh(job)
    return job


def retry_scan(db: Session, job_id: str, requested_by: str | None = None) -> ScanJob:
    old_job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not old_job:
        raise ValueError(f"Scan job {job_id} not found")
    if old_job.status not in RETRYABLE_STATUSES:
        raise ValueError(f"Scan job {job_id} is in status {old_job.status}, cannot retry")
    new_attempt = (old_job.attempt or 1) + 1
    new_job = create_scan_job(
        db, old_job.repository_id, scan_type=old_job.scan_type,
        branch=old_job.branch, requested_by=requested_by,
        previous_scan_id=old_job.id, attempt=new_attempt,
    )
    _emit_journal_event(db, new_job, "scan.retried", {
        "scan_id": new_job.id, "previous_scan_id": old_job.id,
        "repository_id": old_job.repository_id, "attempt": new_attempt,
        "requested_by": requested_by,
    })
    db.commit()
    return new_job


def _run_scan(db: Session, job: ScanJob) -> None:
    """Execute real EVOSIA Core pipeline stages with per-stage timing."""
    repo = db.query(Repository).filter(Repository.id == job.repository_id).first()
    if not repo:
        raise ValueError("Repository not found")

    timings: dict[str, Any] = {}
    state: dict[str, Any] = {}
    for stage in SCAN_STAGES:
        if job.status == "cancelled":
            return
        job.current_stage = stage
        stage_start = datetime.now(timezone.utc)
        _add_history(db, job, stage, "running")
        db.commit()
        try:
            _execute_stage(db, job, repo, stage, timings, state)
        except Exception as e:
            stage_end = datetime.now(timezone.utc)
            timings[stage] = {
                "started_at": _fmt_dt(stage_start),
                "completed_at": _fmt_dt(stage_end),
                "duration_seconds": _elapsed_seconds(stage_start, stage_end),
                "error": str(e)[:500],
            }
            job.stage_timings = timings
            raise
        stage_end = datetime.now(timezone.utc)
        timings[stage] = {
            "started_at": _fmt_dt(stage_start),
            "completed_at": _fmt_dt(stage_end),
            "duration_seconds": _elapsed_seconds(stage_start, stage_end),
        }
        job.stage_timings = timings
        stages_completed = list(job.stages_completed or [])
        stages_completed.append(stage)
        job.stages_completed = stages_completed
        _add_history(db, job, stage, "completed")
        _emit_journal_event(db, job, f"scan.{stage}.completed", {
            "scan_id": job.id, "repository_id": job.repository_id,
            "stage": stage, "duration_seconds": timings[stage]["duration_seconds"],
        })
        db.commit()


def _execute_stage(db, job, repo, stage, timings, state):
    from .hermes_core import (
        materialize_repository, run_readiness, run_repository_intelligence,
        run_engineering_intelligence, run_governance, run_mission_recommendation,
    )

    if stage == "metadata":
        _sync_metadata(db, repo)
    elif stage == "materialization":
        if repo.provider == "github" and repo.identifier:
            path, sha = materialize_repository(repo.identifier, ref=job.branch)
            state["materialized_path"] = str(path)
            state["commit_sha"] = sha
            job.commit_sha = sha
            repo.commit_sha = sha
    elif stage == "readiness":
        mat_path = _get_mat_path(state)
        if mat_path:
            result = run_readiness(mat_path)
            repo.metadata_json = {**(repo.metadata_json or {}), "readiness": result}
            if not result.get("execution_allowed", False):
                raise RuntimeError(
                    f"Readiness blocked: {', '.join(result.get('reasons', ['unknown']))}"
                )
    elif stage == "repository_intelligence":
        mat_path = _get_mat_path(state)
        if mat_path:
            ri = run_repository_intelligence(mat_path)
            repo.metadata_json = {**(repo.metadata_json or {}), "repository_intelligence": ri}
            state["ri"] = ri
    elif stage == "engineering_intelligence":
        ri = state.get("ri")
        if ri:
            ei = run_engineering_intelligence(ri)
            repo.metadata_json = {**(repo.metadata_json or {}), "engineering_intelligence": ei}
            state["ei"] = ei
    elif stage == "governance":
        ei = state.get("ei")
        if ei:
            gov = run_governance(ei)
            repo.metadata_json = {**(repo.metadata_json or {}), "governance": gov}
            state["governance"] = gov
    elif stage == "mission_recommendation":
        gov = state.get("governance")
        if gov:
            missions = run_mission_recommendation(gov)
            repo.metadata_json = {**(repo.metadata_json or {}), "mission_recommendation": missions}
            state["missions"] = missions
    elif stage == "persistence":
        _persist_results(db, job, repo, state)
    elif stage == "journal":
        pass


def _persist_results(db, job, repo, state):
    ei = state.get("ei")
    if ei:
        for f in ei.get("findings", []):
            finding = Finding(
                repository_id=repo.id,
                finding_type=f.get("category", "unknown"),
                severity=f.get("severity", "info"),
                category=f.get("category", "general"),
                title=f.get("title", ""),
                description=f.get("explanation", ""),
                module=_extract_module(f),
                priority_score=f.get("priority_score"),
                effort=f.get("estimated_effort"),
                status="open",
                metadata_json={
                    "evidence_references": f.get("evidence_references", []),
                    "affected_components": f.get("affected_components", []),
                    "finding_id": f.get("finding_id", ""),
                },
            )
            db.add(finding)
        job.findings_count = len(ei.get("findings", []))
        repo.findings_count = (repo.findings_count or 0) + job.findings_count

    gov = state.get("governance")
    if gov:
        for d in gov.get("assessment", {}).get("approval_decisions", []):
            _emit_journal_event(db, job, "governance.decision", {
                "scan_id": job.id, "repository_id": repo.id,
                "finding_id": d.get("finding_id", ""),
                "decision": d.get("decision", ""),
                "rationale": d.get("rationale", ""),
            })

    missions = state.get("missions")
    if missions:
        from ..models import Mission
        for m in missions.get("draft_missions", []):
            mid = m.get("mission_id", "")
            existing = db.query(Mission).filter(
                Mission.mission_id == mid,
                Mission.repository_id == repo.id,
            ).first()
            if existing:
                continue
            mission = Mission(
                mission_id=mid,
                repository_id=repo.id,
                title=m.get("title", ""),
                description=m.get("description", ""),
                mission_type=m.get("mission_type", ""),
                status="pending",
                priority=int(m.get("priority_score", 0)),
                configuration={
                    "objective": m.get("objective", ""),
                    "estimated_effort": m.get("estimated_effort", ""),
                    "originating_finding_id": m.get("originating_finding_id", ""),
                },
            )
            db.add(mission)


def _get_mat_path(state):
    p = state.get("materialized_path")
    if p:
        return Path(p)
    return None


def _extract_module(finding):
    components = finding.get("affected_components", [])
    if components and isinstance(components, list) and len(components) > 0:
        c = components[0]
        if isinstance(c, dict):
            return c.get("component_path") or c.get("component_name")
    return None


def _sync_metadata(db, repo):
    if repo.provider != "github" or not repo.identifier:
        return
    try:
        from .github_integration import sync_repository_from_github
        sync_repository_from_github(db, repo)
    except Exception as e:
        logger.warning("Metadata sync failed for %s: %s", repo.id, e)


def _add_history(db, job, stage, status, message=None):
    entry = ScanHistory(scan_job_id=job.id, stage=stage, status=status, message=message)
    db.add(entry)
    return entry


def _emit_journal_event(db, job, event_type, payload):
    import hashlib
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond:06d}Z"
    payload_str = str(sorted(payload.items()))
    payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
    raw = f"{ts}|{event_type}|{payload_hash}"
    eid = hashlib.sha256(raw.encode()).hexdigest()[:16]
    ev = JournalEvent(
        event_id=eid, timestamp=ts, event_type=event_type, stage="scan",
        repository_id=job.repository_id, actor=job.requested_by or "system",
        payload=payload, payload_sha256=payload_hash,
    )
    db.add(ev)


def _classify_error(e):
    msg = str(e).lower()
    if "auth" in msg or "permission" in msg or "401" in msg or "403" in msg:
        return "auth_error"
    if "not found" in msg or "404" in msg:
        return "not_found"
    if "rate limit" in msg or "429" in msg:
        return "rate_limit"
    if "timeout" in msg:
        return "timeout"
    if "network" in msg or "connection" in msg:
        return "network_error"
    if "readiness blocked" in msg:
        return "readiness_blocked"
    return "unknown"


def _elapsed_seconds(start, end):
    if not start or not end:
        return None
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=timezone.utc)
    elif start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return (end - start).total_seconds()


def _fmt_dt(dt):
    if not dt:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:06d}Z"


def get_scan_status(db, job_id):
    return db.query(ScanJob).filter(ScanJob.id == job_id).first()


def list_scan_jobs(db, repository_id=None, status=None, limit=50, offset=0):
    q = db.query(ScanJob)
    if repository_id:
        q = q.filter(ScanJob.repository_id == repository_id)
    if status:
        q = q.filter(ScanJob.status == status)
    return q.order_by(ScanJob.created_at.desc()).offset(offset).limit(limit).all()
