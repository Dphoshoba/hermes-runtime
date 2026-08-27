"""Add truncation tracking to agent_jobs (LA5).

Adds `truncated` boolean column to `agent_jobs` table so the cloud
can report whether a Local Agent scan hit resource limits.

This migration extends 007_local_agent_scan_jobs.

Revision ID: 008_agent_job_truncation
Revises: 007_local_agent_scan_jobs
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_agent_job_truncation"
down_revision: Union[str, None] = "007_local_agent_scan_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_jobs",
        sa.Column(
            "truncated",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_jobs", "truncated")
