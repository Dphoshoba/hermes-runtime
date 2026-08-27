"""Device business logic — registration, heartbeat, revocation."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Device, User
from ..schemas import DeviceRegister, DeviceRegisterResponse
from .device_auth import create_bootstrap_token, create_device_token


def _generate_device_id() -> str:
    """Generate a unique device identifier."""
    return f"dev_{secrets.token_hex(16)}"


def register_device(
    db: Session,
    user: User,
    body: DeviceRegister,
) -> DeviceRegisterResponse:
    """Register a new device and return a bootstrap token.

    The device is created in 'pending' status until the agent exchanges
    the bootstrap token for a device credential.
    """
    device_id = _generate_device_id()

    device = Device(
        device_id=device_id,
        device_name=body.device_name,
        platform=body.platform,
        agent_version=body.agent_version,
        user_id=user.id,
        status="pending",
        capabilities=body.capabilities,
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    bootstrap_token, expires_at = create_bootstrap_token(db, device_id, user.id)

    return DeviceRegisterResponse(
        bootstrap_token=bootstrap_token,
        expires_at=expires_at,
        device_id=device_id,
    )


def exchange_bootstrap_token(
    db: Session,
    bootstrap_token_payload: dict,
) -> tuple[str, datetime]:
    """Exchange a valid bootstrap token for a device credential.

    Transitions device from 'pending' to 'active'.
    Returns (device_token, expires_at).
    """
    device_id = bootstrap_token_payload["sub"]
    user_id = bootstrap_token_payload["user_id"]

    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    if device.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device does not belong to this user",
        )

    if device.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device is already {device.status}",
        )

    # Activate the device
    device.status = "active"
    device.registered_at = datetime.now(timezone.utc)
    db.commit()

    # Issue device credential
    device_token, expires_at = create_device_token(device_id, user_id)

    return device_token, expires_at


def get_device(db: Session, device_id: str) -> Device:
    """Retrieve a device by device_id."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return device


def list_devices(db: Session, user_id: str) -> list[Device]:
    """List all devices for a user."""
    return db.query(Device).filter(Device.user_id == user_id).all()


def revoke_device(db: Session, device_id: str, user_id: str) -> Device:
    """Revoke a device, preventing further heartbeats and job execution."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    if device.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device does not belong to this user",
        )

    if device.status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device is already revoked",
        )

    device.status = "revoked"
    device.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)

    return device


def record_heartbeat(db: Session, device: Device) -> None:
    """Update the last_seen_at timestamp for a device."""
    device.last_seen_at = datetime.now(timezone.utc)
    db.commit()
