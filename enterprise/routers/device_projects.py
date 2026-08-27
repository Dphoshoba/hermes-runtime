"""Device-projects router — control plane for project authorization and scan jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Device
from ..schemas import (
    DeviceProjectCreate, DeviceProjectResponse,
    AgentScanJobCreate, AgentJobResponse,
)
from ..services import get_current_user
from ..services.project_auth import verify_project_authorization_token
from ..services.device_project_service import (
    register_device_project,
    list_device_projects,
    revoke_device_project,
)
from ..services.agent_job_service import create_scan_job, list_jobs_for_project

router = APIRouter(tags=["device-projects"])


@router.post("/", response_model=DeviceProjectResponse, status_code=201)
def register_project(
    body: DeviceProjectCreate,
    db: Session = Depends(get_db),
) -> DeviceProjectResponse:
    """Register a device-project relationship.

    Requires a valid project authorization token (not device JWT).
    The token must be created by an authenticated user first.
    """
    # Verify project authorization token
    token_payload = verify_project_authorization_token(db, body.project_authorization_token)

    # Verify token device_id matches request
    if token_payload["device_id"] != body.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match device",
        )

    project = register_device_project(db, body, token_payload["user_id"])
    return DeviceProjectResponse.model_validate(project)


@router.get("/", response_model=list[DeviceProjectResponse])
def list_projects(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeviceProjectResponse]:
    """List active projects for a device."""
    projects = list_device_projects(db, device_id)
    # Verify user owns the device
    from ..models import Device
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device or device.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return [DeviceProjectResponse.model_validate(p) for p in projects]


@router.post("/{project_id}/revoke", response_model=DeviceProjectResponse)
def revoke_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceProjectResponse:
    """Revoke a device-project relationship."""
    project = revoke_device_project(db, project_id, user.id)
    return DeviceProjectResponse.model_validate(project)


@router.post("/{project_id}/scans", response_model=AgentJobResponse, status_code=201)
def create_project_scan(
    project_id: str,
    body: AgentScanJobCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentJobResponse:
    """User-authorized: create a governed PROJECT_SCAN job.

    This is the ONLY way to create scan authority for a Local Agent.
    The agent itself must NEVER create scan jobs.

    Requires:
    - Authenticated user (not device token)
    - User owns the device
    - Device is active
    - Device project is active
    - Project authority permits REVIEW_ONLY scanning
    - Operation type is exactly PROJECT_SCAN
    """
    from ..models import DeviceProject
    project = db.query(DeviceProject).filter(
        DeviceProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device project not found",
        )

    job = create_scan_job(
        db=db,
        user_id=user.id,
        device_id=project.device_id,
        device_project_id=project_id,
        operation_type=body.operation_type,
    )
    return AgentJobResponse.model_validate(job)


@router.get("/{project_id}/jobs", response_model=list[AgentJobResponse])
def list_project_jobs(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentJobResponse]:
    """User-authorized: list agent scan jobs for a device project."""
    from ..models import DeviceProject
    project = db.query(DeviceProject).filter(
        DeviceProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device project not found",
        )
    device = db.query(Device).filter(Device.device_id == project.device_id).first()
    if not device or device.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    jobs = list_jobs_for_project(db, project_id, limit=limit, offset=offset)
    return [AgentJobResponse.model_validate(j) for j in jobs]
