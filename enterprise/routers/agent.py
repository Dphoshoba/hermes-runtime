"""Agent router — agent-plane endpoints for Local Agent communication."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import DeviceHeartbeatRequest, DeviceHeartbeatResponse
from ..services.device_auth import verify_device_token
from ..services.device_service import get_device, record_heartbeat

router = APIRouter(prefix="/agent", tags=["agent"])


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

    # LA1: No jobs to dispatch yet — return empty list
    return DeviceHeartbeatResponse(
        status="ok",
        pending_jobs=[],
    )
