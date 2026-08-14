"""Tenant / Workspace isolation for hosted beta (M2).

Adds workspace_id canonical authority boundary. Every externally accessible
beta-owned entity belongs to a workspace. Cross-tenant access is enforced
in the backend service layer.

This module provides:
- WorkspaceContext: current workspace resolution from request
- require_workspace: dependency that validates workspace access
- Workspace-scoped query helpers
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from ..database import get_db
from ..models import User, UserWorkspace


class WorkspaceContext:
    """Resolved workspace for the current request."""

    def __init__(self, workspace_id: str, user_id: str, is_admin: bool = False):
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.is_admin = is_admin


async def require_workspace(
    request: Request,
    db = Depends(get_db),
) -> WorkspaceContext:
    """Resolve and validate workspace from request.

    Resolution order:
    1. X-Workspace-ID header (for API clients)
    2. Query param workspace_id
    3. Default workspace for the authenticated user

    Raises 403 if user does not belong to the workspace.
    """
    user = request.state.user
    workspace_id = (
        request.headers.get("X-Workspace-ID")
        or request.query_params.get("workspace_id")
    )

    if workspace_id:
        # Verify membership
        membership = (
            db.query(UserWorkspace)
            .filter(
                UserWorkspace.user_id == user.id,
                UserWorkspace.workspace_id == workspace_id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied for this workspace")
        return WorkspaceContext(workspace_id=workspace_id, user_id=user.id, is_admin=membership.role == "admin")

    # Default: get user's first workspace
    default = (
        db.query(UserWorkspace)
        .filter(UserWorkspace.user_id == user.id)
        .first()
    )
    if not default:
        raise HTTPException(status_code=403, detail="No workspace access")
    return WorkspaceContext(workspace_id=default.workspace_id, user_id=user.id, is_admin=default.role == "admin")
