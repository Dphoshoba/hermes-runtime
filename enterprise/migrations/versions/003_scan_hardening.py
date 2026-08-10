"""Add scan job hardening fields and stage timings

Revision ID: 003_scan_hardening
Revises: 002_scan_jobs
Create Date: 2026-08-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_scan_hardening"
down_revision: Union[str, None] = "002_scan_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scan_jobs", sa.Column("attempt", sa.Integer, server_default="1"))
    op.add_column("scan_jobs", sa.Column("previous_scan_id", sa.String(36), sa.ForeignKey("scan_jobs.id")))
    op.add_column("scan_jobs", sa.Column("requested_by", sa.String(255)))
    op.add_column("scan_jobs", sa.Column("cancellation_requested_at", sa.DateTime))
    op.add_column("scan_jobs", sa.Column("cancelled_at", sa.DateTime))
    op.add_column("scan_jobs", sa.Column("failure_classification", sa.String(100)))
    op.add_column("scan_jobs", sa.Column("stage_timings", sa.JSON, default=dict))


def downgrade() -> None:
    op.drop_column("scan_jobs", "stage_timings")
    op.drop_column("scan_jobs", "failure_classification")
    op.drop_column("scan_jobs", "cancelled_at")
    op.drop_column("scan_jobs", "cancellation_requested_at")
    op.drop_column("scan_jobs", "requested_by")
    op.drop_column("scan_jobs", "previous_scan_id")
    op.drop_column("scan_jobs", "attempt")
