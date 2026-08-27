"""Agent router — agent-plane endpoints for Local Agent communication."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    DeviceHeartbeatRequest, DeviceHeartbeatResponse,
    AgentJobResponse, AgentJobStartedRequest, AgentJobResultsRequest,
    AgentJobFailedRequest, JOB_STATUS_PENDING,
)
from ..services.device_auth import verify_device_token
from ..services.device_service import get_device, record_heartbeat
from ..services.agent_job_service import (
    get_next_job, get_job, mark_job_started, complete_job, fail_job,
)

router = APIRouter(tags=["agent"])


def _get_device_from_token(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Extract and verify device token from Authorization header.

    Returns decoded device payload.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[7:]  # Remove "Bearer " prefix
    payload = verify_device_token(token)

    # Verify device exists and is active
    device = get_device(db, payload["sub"])
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device is {device.status}",
        )

    # Verify token user_id matches device owner
    if device.user_id != payload.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match device owner",
        )

    return payload


@router.post("/heartbeat", response_model=DeviceHeartbeatResponse)
def heartbeat(
    body: DeviceHeartbeatRequest,
    device_payload: dict = Depends(_get_device_from_token),
    db: Session = Depends(get_db),
) -> DeviceHeartbeatResponse:
    """Agent-initiated heartbeat. Requires valid device credential.

    The Authorization header must contain a valid device JWT.
    The device_id in the token must match the device_id in the body.
    """
    # Verify the device_id in the token matches the request body
    if device_payload["sub"] != body.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device ID mismatch between token and request body",
        )

    device = get_device(db, body.device_id)

    # Record heartbeat
    record_heartbeat(db, device)

    # Check for pending jobs
    pending_job = get_next_job(db, body.device_id)
    pending_jobs = []
    if pending_job:
        pending_jobs = [pending_job.id]

    return DeviceHeartbeatResponse(
        status="ok",
        pending_jobs=pending_jobs,
    )


# ---------------------------------------------------------------------------
# Agent Work-Plane: Job Endpoints
# ---------------------------------------------------------------------------

@router.get("/jobs/next", response_model=AgentJobResponse | None)
def get_next_agent_job(
    device_payload: dict = Depends(_get_device_from_token),
    db: Session = Depends(get_db),
) -> AgentJobResponse | None:
    """Agent fetches the next pending job for this device.

    Returns null if no jobs available.
    """
    device_id = device_payload["sub"]
    job = get_next_job(db, device_id)
    if not job:
        return None
    return AgentJobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=AgentJobResponse)
def get_agent_job(
    job_id: str,
    device_payload: dict = Depends(_get_device_from_token),
    db: Session = Depends(get_db),
) -> AgentJobResponse:
    """Agent fetches a specific job.

    Validates job belongs to this device.
    """
    device_id = device_payload["sub"]
    job = get_job(db, job_id, device_id)
    return AgentJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/started", response_model=AgentJobResponse)
def mark_job_started_endpoint(
    job_id: str,
    body: AgentJobStartedRequest,
    device_payload: dict = Depends(_get_device_from_token),
    db: Session = Depends(get_db),
) -> AgentJobResponse:
    """Agent reports job started.

    Transitions job from PENDING to STARTED.
    """
    device_id = device_payload["sub"]
    job = get_job(db, job_id, device_id)
    job = mark_job_started(db, job)
    return AgentJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/results", response_model=AgentJobResponse)
def submit_job_results(
    job_id: str,
    body: AgentJobResultsRequest,
    device_payload: dict = Depends(_get_device_from_token),
    db: Session = Depends(get_db),
) -> AgentJobResponse:
    """Agent submits governed scan results.

    Validates:
    - job belongs to this device
    - job is in STARTED state
    - evidence has correct provenance
    """
    device_id = device_payload["sub"]
    job = get_job(db, job_id, device_id)

    # Validate evidence provenance
    evidence = body.evidence
    if evidence.get("provenance") != "LIVE_EVOSIA_EVIDENCE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid evidence provenance",
        )
    if evidence.get("evidence_source") != "device_local_scan":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid evidence source",
        )
    if evidence.get("device_id") != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evidence device_id does not match",
        )
    if evidence.get("job_id") != job_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evidence job_id does not match",
        )

    job = complete_job(db, job)
    return AgentJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/failed", response_model=AgentJobResponse)
def report_job_failed(
    job_id: str,
    body: AgentJobFailedRequest,
    device_payload: dict = Depends(_get_device_from_token),
    db: Session = Depends(get_db),
) -> AgentJobResponse:
    """Agent reports job failure.

    Validates job belongs to this device.
    """
    device_id = device_payload["sub"]
    job = get_job(db, job_id, device_id)
    job = fail_job(db, job, body.failure_reason)
    return AgentJobResponse.model_validate(job)
