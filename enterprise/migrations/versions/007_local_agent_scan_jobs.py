"""Add Local Agent governed scan jobs (LA4).

Creates:
- `agent_jobs` table for governed PROJECT_SCAN jobs

This migration extends 006_local_agent_projects.

Revision ID: 007_local_agent_scan_jobs
Revises: 006_local_agent_projects
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_local_agent_scan_jobs"
down_revision: Union[str, None] = "006_local_agent_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.device_id"), nullable=False, index=True),
        sa.Column("device_project_id", sa.String(36), sa.ForeignKey("device_projects.id"), nullable=False, index=True),
        sa.Column("operation_type", sa.String(50), nullable=False, server_default="PROJECT_SCAN"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING", index=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("failed_at", sa.DateTime, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_jobs")
