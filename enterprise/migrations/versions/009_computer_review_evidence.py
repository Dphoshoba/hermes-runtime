"""Persist computer review evidence and link downstream records.

Revision ID: 009_computer_review_evidence
Revises: 008_agent_job_truncation
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_computer_review_evidence"
down_revision: Union[str, None] = "008_agent_job_truncation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE agent_jobs SET failure_reason = 'Review request expired' "
        "WHERE status = 'EXPIRED' AND failure_reason IS NULL"
    ))
    bind.execute(sa.text(
        "UPDATE agent_jobs SET status = CASE status "
        "WHEN 'PENDING' THEN 'QUEUED' "
        "WHEN 'STARTED' THEN 'RUNNING' "
        "WHEN 'EXPIRED' THEN 'FAILED' "
        "ELSE status END"
    ))

    with op.batch_alter_table("agent_jobs") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(30),
            existing_server_default="PENDING",
            server_default="QUEUED",
            nullable=False,
        )
        batch_op.add_column(sa.Column("idempotency_key", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("evidence", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("coverage", sa.JSON(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_agent_jobs_idempotency_key",
            ["user_id", "device_project_id", "idempotency_key"],
        )

    with op.batch_alter_table("scan_jobs") as batch_op:
        batch_op.alter_column("repository_id", existing_type=sa.String(36), nullable=True)
        batch_op.add_column(sa.Column("review_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_scan_jobs_review_id_agent_jobs",
            "agent_jobs",
            ["review_id"],
            ["id"],
        )
        batch_op.create_unique_constraint("uq_scan_jobs_review_id", ["review_id"])

    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("review_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_reports_review_id_agent_jobs",
            "agent_jobs",
            ["review_id"],
            ["id"],
        )
        batch_op.create_unique_constraint("uq_reports_review_id", ["review_id"])

    with op.batch_alter_table("findings") as batch_op:
        batch_op.add_column(sa.Column("review_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_findings_review_id_agent_jobs",
            "agent_jobs",
            ["review_id"],
            ["id"],
        )
        batch_op.add_column(sa.Column("scan_job_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_findings_scan_job_id_scan_jobs",
            "scan_jobs",
            ["scan_job_id"],
            ["id"],
        )

    op.create_index("ix_findings_review_id", "findings", ["review_id"])
    op.create_index("ix_findings_scan_job_id", "findings", ["scan_job_id"])


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE agent_jobs SET failure_reason = 'Review cancelled' "
        "WHERE status = 'CANCELLED' AND failure_reason IS NULL"
    ))
    bind.execute(sa.text(
        "UPDATE agent_jobs SET status = CASE status "
        "WHEN 'QUEUED' THEN 'PENDING' "
        "WHEN 'RUNNING' THEN 'STARTED' "
        "WHEN 'PARTIAL' THEN 'COMPLETED' "
        "WHEN 'CANCELLED' THEN 'FAILED' "
        "ELSE status END"
    ))

    op.drop_index("ix_findings_scan_job_id", table_name="findings")
    op.drop_index("ix_findings_review_id", table_name="findings")

    with op.batch_alter_table("findings") as batch_op:
        batch_op.drop_constraint("fk_findings_scan_job_id_scan_jobs", type_="foreignkey")
        batch_op.drop_constraint("fk_findings_review_id_agent_jobs", type_="foreignkey")
        batch_op.drop_column("scan_job_id")
        batch_op.drop_column("review_id")

    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_constraint("uq_reports_review_id", type_="unique")
        batch_op.drop_constraint("fk_reports_review_id_agent_jobs", type_="foreignkey")
        batch_op.drop_column("review_id")

    with op.batch_alter_table("scan_jobs") as batch_op:
        batch_op.drop_constraint("uq_scan_jobs_review_id", type_="unique")
        batch_op.drop_constraint("fk_scan_jobs_review_id_agent_jobs", type_="foreignkey")
        batch_op.drop_column("review_id")
        batch_op.alter_column("repository_id", existing_type=sa.String(36), nullable=False)

    with op.batch_alter_table("agent_jobs") as batch_op:
        batch_op.drop_constraint("uq_agent_jobs_idempotency_key", type_="unique")
        batch_op.drop_column("coverage")
        batch_op.drop_column("evidence")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("idempotency_key")
        batch_op.alter_column(
            "status",
            existing_type=sa.String(30),
            server_default="PENDING",
            nullable=False,
        )
