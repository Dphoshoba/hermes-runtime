"""Device-project service — registration, listing, revocation."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Device, DeviceProject
from ..schemas import DeviceProjectCreate


def register_device_project(
    db: Session,
    body: DeviceProjectCreate,
    user_id: str,
) -> DeviceProject:
    """Register a device-project relationship."""
    # Verify device exists and belongs to user
    device = db.query(Device).filter(Device.device_id == body.device_id).first()
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

    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is {device.status}",
        )

    # Check for duplicate registration using fingerprint (project identity)
    if body.local_root_fingerprint:
        existing = db.query(DeviceProject).filter(
            DeviceProject.device_id == body.device_id,
            DeviceProject.local_root_fingerprint == body.local_root_fingerprint,
            DeviceProject.status == "active",
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project already registered for this device",
            )

    project = DeviceProject(
        device_id=body.device_id,
        user_id=user_id,
        display_name=body.display_name,
        local_root_fingerprint=body.local_root_fingerprint,
        status="active",
        authority="REVIEW_ONLY",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_device_projects(db: Session, device_id: str) -> list[DeviceProject]:
    """List all active projects for a device."""
    return db.query(DeviceProject).filter(
        DeviceProject.device_id == device_id,
        DeviceProject.status == "active",
    ).all()


def revoke_device_project(
    db: Session,
    project_id: str,
    user_id: str,
) -> DeviceProject:
    """Revoke a device-project relationship."""
    project = db.query(DeviceProject).filter(DeviceProject.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project does not belong to this user",
        )

    if project.status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is already revoked",
        )

    project.status = "revoked"
    project.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project
