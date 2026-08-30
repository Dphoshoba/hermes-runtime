"""Project authorization service — browser-assisted project authorization logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import ProjectAuthorizationRequest, DeviceProject, Device
from ..schemas import ProjectAuthorizationRequestCreate, ProjectAuthorizationRequestResponse


# Project authorization request lifetime: 10 minutes
PROJECT_AUTH_REQUEST_EXPIRE_MINUTES = 10

# Request ID prefix for identification
REQUEST_ID_PREFIX = "proj_auth_"


def _generate_request_id() -> str:
    """Generate a high-entropy opaque project authorization request identifier."""
    return f"{REQUEST_ID_PREFIX}{secrets.token_urlsafe(32)}"


def _is_expired(request: ProjectAuthorizationRequest) -> bool:
    """Check if a project authorization request has expired."""
    expires_at = request.expires_at.replace(tzinfo=None) if request.expires_at.tzinfo else request.expires_at
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    return expires_at < now_utc


def create_project_authorization_request(
    db: Session,
    body: ProjectAuthorizationRequestCreate,
    device_id: str,
    cloud_url: str,
) -> ProjectAuthorizationRequestResponse:
    """Create a short-lived project authorization request.

    The Connector initiates project authorization by creating a request with
    project metadata. The user then approves it in the browser.
    """
    # Verify device exists and is active
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not active",
        )

    request_id = _generate_request_id()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PROJECT_AUTH_REQUEST_EXPIRE_MINUTES)

    request = ProjectAuthorizationRequest(
        request_id=request_id,
        device_id=device_id,
        display_name=body.display_name,
        local_root_fingerprint=body.local_root_fingerprint,
        platform=body.platform,
        agent_version=body.agent_version,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(request)
    db.commit()

    authorization_url = f"{cloud_url.rstrip('/')}/authorize-project?id={request_id}"

    return ProjectAuthorizationRequestResponse(
        request_id=request_id,
        authorization_url=authorization_url,
        expires_at=expires_at,
    )


def get_project_authorization_status(db: Session, request_id: str) -> ProjectAuthorizationRequest:
    """Get project authorization request by ID, validating it exists and hasn't expired."""
    request = db.query(ProjectAuthorizationRequest).filter(
        ProjectAuthorizationRequest.request_id == request_id
    ).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project authorization request not found",
        )

    if _is_expired(request) and request.status == "PENDING":
        request.status = "EXPIRED"
        db.commit()
        db.refresh(request)

    return request


def approve_project_authorization(
    db: Session,
    request_id: str,
    user_id: str,
) -> ProjectAuthorizationRequest:
    """Approve a project authorization request.

    Binds the request to the approving user and transitions to APPROVED.
    """
    request = db.query(ProjectAuthorizationRequest).filter(
        ProjectAuthorizationRequest.request_id == request_id
    ).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project authorization request not found",
        )

    if _is_expired(request):
        request.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Project authorization request has expired",
        )

    if request.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project authorization request is already {request.status}",
        )

    request.user_id = user_id
    request.status = "APPROVED"
    request.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)

    return request


def deny_project_authorization(
    db: Session,
    request_id: str,
) -> ProjectAuthorizationRequest:
    """Deny a project authorization request."""
    request = db.query(ProjectAuthorizationRequest).filter(
        ProjectAuthorizationRequest.request_id == request_id
    ).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project authorization request not found",
        )

    if request.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project authorization request is already {request.status}",
        )

    request.status = "DENIED"
    db.commit()
    db.refresh(request)

    return request


def consume_project_authorization(
    db: Session,
    request_id: str,
) -> tuple[str, str]:
    """Consume an approved project authorization request to create DeviceProject.

    Returns (device_project_id, user_id).
    Enforces single-use: marks request as CONSUMED.
    """
    request = db.query(ProjectAuthorizationRequest).filter(
        ProjectAuthorizationRequest.request_id == request_id
    ).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project authorization request not found",
        )

    if _is_expired(request):
        request.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Project authorization request has expired",
        )

    if request.status == "CONSUMED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project authorization request already consumed",
        )

    if request.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project authorization request is {request.status}, not approved",
        )

    if not request.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project authorization request has no approving user",
        )

    # Check for existing authorization (idempotent)
    existing = db.query(DeviceProject).filter(
        DeviceProject.device_id == request.device_id,
        DeviceProject.local_root_fingerprint == request.local_root_fingerprint,
        DeviceProject.status == "active",
    ).first()

    if existing:
        # Already authorized — mark as consumed and return existing
        request.status = "CONSUMED"
        request.consumed_at = datetime.now(timezone.utc)
        db.commit()
        return existing.id, request.user_id

    # Create DeviceProject with REVIEW_ONLY authority
    device_project = DeviceProject(
        device_id=request.device_id,
        user_id=request.user_id,
        display_name=request.display_name,
        local_root_fingerprint=request.local_root_fingerprint,
        status="active",
        authority="REVIEW_ONLY",
        registered_at=datetime.now(timezone.utc),
    )
    db.add(device_project)

    # Mark request as consumed
    request.status = "CONSUMED"
    request.consumed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device_project)

    return device_project.id, request.user_id
