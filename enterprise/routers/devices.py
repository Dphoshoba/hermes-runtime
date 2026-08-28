"""Device router — control plane endpoints for device management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    DeviceRegister,
    DeviceRegisterResponse,
    DeviceResponse,
    DeviceTokenExchange,
    DeviceTokenResponse,
    ProjectAuthorizationTokenCreate,
    ProjectAuthorizationTokenResponse,
)
from ..services import get_current_user
from ..services.device_auth import verify_bootstrap_token
from ..services.project_auth import create_project_authorization_token
from ..services.device_service import (
    register_device,
    exchange_bootstrap_token,
    get_device,
    list_devices,
    revoke_device,
)

router = APIRouter(tags=["devices"])


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
def register_new_device(
    body: DeviceRegister,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceRegisterResponse:
    """User-authorized: register a new device and receive a bootstrap token."""
    return register_device(db, user, body)


@router.post("/exchange", response_model=DeviceTokenResponse)
def exchange_token(
    body: DeviceTokenExchange,
    db: Session = Depends(get_db),
) -> DeviceTokenResponse:
    """Agent-authorized: exchange bootstrap token for device credential."""
    payload = verify_bootstrap_token(db, body.bootstrap_token)
    device_token, expires_at = exchange_bootstrap_token(db, payload)
    return DeviceTokenResponse(
        device_id=payload["sub"],
        access_token=device_token,
        token_type="device",
        expires_at=expires_at,
    )


@router.get("/", response_model=list[DeviceResponse])
def list_all_devices(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeviceResponse]:
    """User-authorized: list all devices for the current user."""
    devices = list_devices(db, user.id)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device_details(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """User-authorized: get device details."""
    device = get_device(db, device_id)
    if device.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return DeviceResponse.model_validate(device)


@router.post("/{device_id}/revoke", response_model=DeviceResponse)
def revoke_device_endpoint(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    """User-authorized: revoke a device."""
    device = revoke_device(db, device_id, user.id)
    return DeviceResponse.model_validate(device)


@router.post("/{device_id}/project-auth-token", response_model=ProjectAuthorizationTokenResponse)
def create_project_auth_token(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAuthorizationTokenResponse:
    """User-authorized: create a short-lived project authorization token.

    This token allows the device to register a new project without
    needing the user's password or full credentials.
    """
    # Verify user owns the device
    device = get_device(db, device_id)
    if device.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is {device.status}",
        )

    token, expires_at = create_project_authorization_token(db, device_id, user.id)
    return ProjectAuthorizationTokenResponse(
        project_authorization_token=token,
        expires_at=expires_at,
    )
