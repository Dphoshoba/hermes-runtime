"""Pairing service — browser-assisted device pairing logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import PairingRequest, Device
from ..schemas import PairingRequestCreate, PairingRequestResponse
from .device_auth import create_device_token


# Pairing request lifetime: 5 minutes (same as bootstrap tokens)
PAIRING_REQUEST_EXPIRE_MINUTES = 5

# Pairing ID prefix for identification
PAIRING_ID_PREFIX = "pair_"


def _generate_pairing_id() -> str:
    """Generate a high-entropy opaque pairing identifier."""
    return f"{PAIRING_ID_PREFIX}{secrets.token_urlsafe(32)}"


def create_pairing_request(
    db: Session,
    body: PairingRequestCreate,
    cloud_url: str,
) -> PairingRequestResponse:
    """Create a short-lived pairing request.

    The Connector initiates pairing by creating a request with a high-entropy
    identifier. The user then approves it in the browser.
    """
    pairing_id = _generate_pairing_id()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PAIRING_REQUEST_EXPIRE_MINUTES)

    request = PairingRequest(
        pairing_id=pairing_id,
        device_name=body.device_name,
        platform=body.platform,
        agent_version=body.agent_version,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(request)
    db.commit()

    pairing_url = f"{cloud_url.rstrip('/')}/pair?id={pairing_id}"

    return PairingRequestResponse(
        pairing_id=pairing_id,
        pairing_url=pairing_url,
        expires_at=expires_at,
    )


def _is_expired(request: PairingRequest) -> bool:
    """Check if a pairing request has expired."""
    expires_at = request.expires_at.replace(tzinfo=None) if request.expires_at.tzinfo else request.expires_at
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    return expires_at < now_utc


def get_pairing_status(db: Session, pairing_id: str) -> PairingRequest:
    """Get pairing request by ID, validating it exists and hasn't expired."""
    request = db.query(PairingRequest).filter(PairingRequest.pairing_id == pairing_id).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pairing request not found",
        )

    if _is_expired(request) and request.status == "PENDING":
        request.status = "EXPIRED"
        db.commit()
        db.refresh(request)

    return request


def approve_pairing(
    db: Session,
    pairing_id: str,
    user_id: str,
) -> PairingRequest:
    """Approve a pairing request.

    Binds the request to the approving user and transitions to APPROVED.
    """
    request = db.query(PairingRequest).filter(PairingRequest.pairing_id == pairing_id).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pairing request not found",
        )

    if _is_expired(request):
        request.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Pairing request has expired",
        )

    if request.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pairing request is already {request.status}",
        )

    request.user_id = user_id
    request.status = "APPROVED"
    request.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)

    return request


def deny_pairing(
    db: Session,
    pairing_id: str,
) -> PairingRequest:
    """Deny a pairing request."""
    request = db.query(PairingRequest).filter(PairingRequest.pairing_id == pairing_id).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pairing request not found",
        )

    if request.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pairing request is already {request.status}",
        )

    request.status = "DENIED"
    db.commit()
    db.refresh(request)

    return request


def consume_pairing(
    db: Session,
    pairing_id: str,
) -> tuple[str, str, str]:
    """Consume an approved pairing request to issue a device credential.

    Returns (device_id, device_token, user_id).
    Enforces single-use: marks request as CONSUMED.
    """
    request = db.query(PairingRequest).filter(PairingRequest.pairing_id == pairing_id).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pairing request not found",
        )

    if _is_expired(request):
        request.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Pairing request has expired",
        )

    if request.status == "CONSUMED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pairing request already consumed",
        )

    if request.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pairing request is {request.status}, not approved",
        )

    if not request.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pairing request has no approving user",
        )

    # Create the device
    device_id = f"dev_{secrets.token_hex(16)}"
    device = Device(
        device_id=device_id,
        device_name=request.device_name,
        platform=request.platform,
        agent_version=request.agent_version,
        user_id=request.user_id,
        status="active",
        registered_at=datetime.now(timezone.utc),
    )
    db.add(device)

    # Mark pairing request as consumed
    request.status = "CONSUMED"
    request.consumed_at = datetime.now(timezone.utc)
    db.commit()

    # Issue device credential
    device_token, _ = create_device_token(device_id, request.user_id)

    return device_id, device_token, request.user_id
