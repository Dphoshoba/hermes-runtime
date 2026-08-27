"""Add Local Agent project authorization tables (LA3).

Creates:
- `device_projects` table for explicit project authorization
- `project_authorization_tokens` table for short-lived project auth tokens

This migration extends 005_local_agent_devices.

Revision ID: 006_local_agent_projects
Revises: 005_local_agent_devices
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_local_agent_projects"
down_revision: Union[str, None] = "005_local_agent_devices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.device_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("local_root_fingerprint", sa.String(128)),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("authority", sa.String(50), nullable=False, server_default="REVIEW_ONLY"),
        sa.Column("registered_at", sa.DateTime, nullable=True),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "project_authorization_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.device_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("consumed", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("project_authorization_tokens")
    op.drop_table("device_projects")
