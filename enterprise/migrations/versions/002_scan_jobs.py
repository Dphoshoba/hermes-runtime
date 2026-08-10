"""Add scan jobs, scan history, and GitHub metadata fields

Revision ID: 002_scan_jobs
Revises: 001_initial
Create Date: 2026-08-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_scan_jobs"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add GitHub metadata columns to repositories
    op.add_column("repositories", sa.Column("provider", sa.String(50), server_default="local"))
    op.add_column("repositories", sa.Column("identifier", sa.String(512)))
    op.add_column("repositories", sa.Column("commit_sha", sa.String(40)))
    op.add_column("repositories", sa.Column("visibility", sa.String(50)))
    op.add_column("repositories", sa.Column("last_synced_at", sa.DateTime))

    # Scan Jobs
    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), nullable=False, index=True),
        sa.Column("status", sa.String(50), default="pending", index=True),
        sa.Column("scan_type", sa.String(50), default="full"),
        sa.Column("branch", sa.String(255)),
        sa.Column("commit_sha", sa.String(40)),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("error_message", sa.Text),
        sa.Column("stages_completed", sa.JSON, default=list),
        sa.Column("current_stage", sa.String(100)),
        sa.Column("findings_count", sa.Integer, default=0),
        sa.Column("metadata_json", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # Scan History
    op.create_table(
        "scan_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scan_job_id", sa.String(36), sa.ForeignKey("scan_jobs.id"), nullable=False, index=True),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("metadata_json", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("scan_history")
    op.drop_table("scan_jobs")
    op.drop_column("repositories", "last_synced_at")
    op.drop_column("repositories", "visibility")
    op.drop_column("repositories", "commit_sha")
    op.drop_column("repositories", "identifier")
    op.drop_column("repositories", "provider")
