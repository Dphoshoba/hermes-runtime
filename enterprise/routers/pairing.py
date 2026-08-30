"""Pairing router — browser-assisted device pairing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    PairingRequestCreate,
    PairingRequestResponse,
    PairingStatusResponse,
    PairingApprovalRequest,
    PairingDenialRequest,
    PairingApprovalResponse,
)
from ..services import get_current_user
from ..services.pairing_service import (
    create_pairing_request,
    get_pairing_status,
    approve_pairing,
    deny_pairing,
    consume_pairing,
)

router = APIRouter(tags=["pairing"])


def _get_cloud_url(request: Request) -> str:
    """Derive cloud URL from the request's base URL."""
    base = str(request.base_url).rstrip("/")
    return base


@router.post("/request", response_model=PairingRequestResponse, status_code=201)
def create_pairing(
    body: PairingRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> PairingRequestResponse:
    """Connector-initiated: create a pairing request.

    No user authentication required — the Connector creates a request
    with a high-entropy identifier. The user then approves it in browser.
    """
    cloud_url = _get_cloud_url(request)
    return create_pairing_request(db, body, cloud_url)


@router.get("/{pairing_id}/status", response_model=PairingStatusResponse)
def polling_status(
    pairing_id: str,
    db: Session = Depends(get_db),
) -> PairingStatusResponse:
    """Connector-initiated: poll pairing status.

    Returns current status of the pairing request.
    If approved, includes the device credential for the Connector to consume.
    """
    request = get_pairing_status(db, pairing_id)

    response = PairingStatusResponse(
        pairing_id=request.pairing_id,
        status=request.status,
        expires_at=request.expires_at,
    )

    # If approved, the Connector can now consume the pairing
    if request.status == "APPROVED":
        # Don't consume yet — let the Connector explicitly consume
        pass

    return response


@router.post("/{pairing_id}/consume", response_model=PairingStatusResponse)
def consume_approved_pairing(
    pairing_id: str,
    db: Session = Depends(get_db),
) -> PairingStatusResponse:
    """Connector-initiated: consume an approved pairing request.

    Creates the device and returns the credential.
    """
    device_id, device_token, user_id = consume_pairing(db, pairing_id)

    # Get the updated request to return
    request = get_pairing_status(db, pairing_id)

    return PairingStatusResponse(
        pairing_id=request.pairing_id,
        status=request.status,
        device_credential=device_token,
        device_id=device_id,
        expires_at=request.expires_at,
    )


@router.post("/{pairing_id}/approve", response_model=PairingApprovalResponse)
def approve(
    pairing_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PairingApprovalResponse:
    """User-authenticated: approve a pairing request.

    Binds the request to the authenticated user.
    """
    request = approve_pairing(db, pairing_id, user.id)

    return PairingApprovalResponse(
        pairing_id=request.pairing_id,
        status=request.status,
        device_name=request.device_name,
    )


@router.post("/{pairing_id}/deny", response_model=PairingApprovalResponse)
def deny(
    pairing_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PairingApprovalResponse:
    """User-authenticated: deny a pairing request."""
    request = deny_pairing(db, pairing_id)

    return PairingApprovalResponse(
        pairing_id=request.pairing_id,
        status=request.status,
        device_name=request.device_name,
    )


@router.get("/{pairing_id}")
def get_pairing_info(
    pairing_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Public: get pairing request info for browser display.

    Returns limited info needed for the approval page.
    Does NOT return credentials.
    """
    from ..services.pairing_service import _is_expired

    request = get_pairing_status(db, pairing_id)

    if _is_expired(request) and request.status == "PENDING":
        return {
            "pairing_id": request.pairing_id,
            "status": request.status,
            "device_name": request.device_name,
            "platform": request.platform,
            "expired": True,
        }

    return {
        "pairing_id": request.pairing_id,
        "status": request.status,
        "device_name": request.device_name,
        "platform": request.platform,
        "agent_version": request.agent_version,
        "expired": False,
    }
