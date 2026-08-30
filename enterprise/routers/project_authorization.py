"""Project authorization router — browser-assisted project authorization endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    ProjectAuthorizationRequestCreate,
    ProjectAuthorizationRequestResponse,
    ProjectAuthorizationStatusResponse,
    ProjectAuthorizationApprovalResponse,
)
from ..services import get_current_user
from ..services.project_auth_service import (
    create_project_authorization_request,
    get_project_authorization_status,
    approve_project_authorization,
    deny_project_authorization,
    consume_project_authorization,
)

router = APIRouter(tags=["project-authorization"])


def _get_cloud_url(request: Request) -> str:
    """Derive cloud URL from the request's base URL."""
    base = str(request.base_url).rstrip("/")
    return base


@router.post("/request", response_model=ProjectAuthorizationRequestResponse, status_code=201)
def create_authorization(
    body: ProjectAuthorizationRequestCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAuthorizationRequestResponse:
    """Connector-initiated: create a project authorization request.

    Requires authenticated device identity (paired device).
    The user then approves in browser.
    """
    # For now, we'll use a placeholder device_id from the authenticated user
    # In production, this would come from the device JWT
    # The Connector will pass its device_id in the request
    cloud_url = _get_cloud_url(request)

    # Get device_id from request headers or body
    # For P3d, we'll extract it from the authenticated user's devices
    from ..models import Device
    device = db.query(Device).filter(Device.user_id == user.id, Device.status == "active").first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active device found for user",
        )

    return create_project_authorization_request(db, body, device.device_id, cloud_url)


@router.get("/{request_id}/status", response_model=ProjectAuthorizationStatusResponse)
def polling_status(
    request_id: str,
    db: Session = Depends(get_db),
) -> ProjectAuthorizationStatusResponse:
    """Connector-initiated: poll project authorization status.

    Returns current status of the authorization request.
    """
    request = get_project_authorization_status(db, request_id)

    response = ProjectAuthorizationStatusResponse(
        request_id=request.request_id,
        status=request.status,
        expires_at=request.expires_at,
    )

    return response


@router.post("/{request_id}/consume", response_model=ProjectAuthorizationStatusResponse)
def consume_approved_authorization(
    request_id: str,
    db: Session = Depends(get_db),
) -> ProjectAuthorizationStatusResponse:
    """Connector-initiated: consume an approved project authorization request.

    Creates the DeviceProject and returns the project ID.
    """
    device_project_id, user_id = consume_project_authorization(db, request_id)

    # Get the updated request to return
    request = get_project_authorization_status(db, request_id)

    return ProjectAuthorizationStatusResponse(
        request_id=request.request_id,
        status=request.status,
        device_project_id=device_project_id,
        expires_at=request.expires_at,
    )


@router.post("/{request_id}/approve", response_model=ProjectAuthorizationApprovalResponse)
def approve(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAuthorizationApprovalResponse:
    """User-authenticated: approve a project authorization request.

    Binds the request to the approving user.
    """
    request = approve_project_authorization(db, request_id, user.id)

    return ProjectAuthorizationApprovalResponse(
        request_id=request.request_id,
        status=request.status,
        display_name=request.display_name,
    )


@router.post("/{request_id}/deny", response_model=ProjectAuthorizationApprovalResponse)
def deny(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAuthorizationApprovalResponse:
    """User-authenticated: deny a project authorization request."""
    request = deny_project_authorization(db, request_id)

    return ProjectAuthorizationApprovalResponse(
        request_id=request.request_id,
        status=request.status,
        display_name=request.display_name,
    )


@router.get("/{request_id}")
def get_authorization_info(
    request_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Public: get project authorization request info for browser display.

    Returns limited info needed for the approval page.
    Does NOT return credentials.
    """
    from ..services.project_auth_service import _is_expired

    request = get_project_authorization_status(db, request_id)

    if _is_expired(request) and request.status == "PENDING":
        return {
            "request_id": request.request_id,
            "status": request.status,
            "display_name": request.display_name,
            "platform": request.platform,
            "expired": True,
        }

    return {
        "request_id": request.request_id,
        "status": request.status,
        "display_name": request.display_name,
        "platform": request.platform,
        "agent_version": request.agent_version,
        "expired": False,
    }
