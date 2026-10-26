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
    duplicate_projects = bind.execute(sa.text(
        "SELECT device_project_id FROM agent_jobs "
        "WHERE status IN ('PENDING', 'STARTED', 'QUEUED', 'RUNNING') "
        "GROUP BY device_project_id HAVING COUNT(*) > 1"
    )).scalars().all()
    if duplicate_projects:
        raise RuntimeError(
            "Cannot enforce one active review per project; resolve active duplicate "
            f"agent_jobs first: {', '.join(duplicate_projects)}"
        )

    with op.batch_alter_table("agent_jobs") as batch_op:
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

    op.create_table(
        "agent_job_idempotency_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "device_project_id",
            sa.String(36),
            sa.ForeignKey("device_projects.id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("agent_job_id", sa.String(36), sa.ForeignKey("agent_jobs.id"), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "device_project_id",
            "idempotency_key",
            name="uq_agent_job_idempotency_request",
        ),
    )
    op.create_index(
        "ix_agent_job_idempotency_keys_user_id",
        "agent_job_idempotency_keys",
        ["user_id"],
    )
    op.create_index(
        "ix_agent_job_idempotency_keys_device_project_id",
        "agent_job_idempotency_keys",
        ["device_project_id"],
    )
    op.create_index(
        "ix_agent_job_idempotency_keys_agent_job_id",
        "agent_job_idempotency_keys",
        ["agent_job_id"],
    )

    active_predicate = "status IN ('PENDING', 'STARTED', 'QUEUED', 'RUNNING')"
    op.create_index(
        "uq_agent_jobs_one_active_per_project",
        "agent_jobs",
        ["device_project_id"],
        unique=True,
        postgresql_where=sa.text(active_predicate),
        sqlite_where=sa.text(active_predicate),
    )


def downgrade() -> None:
    bind = op.get_bind()
    evidence_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM agent_jobs "
        "WHERE evidence IS NOT NULL OR coverage IS NOT NULL"
    )).scalar_one()
    key_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM agent_job_idempotency_keys"
    )).scalar_one()
    legacy_key_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM agent_jobs WHERE idempotency_key IS NOT NULL"
    )).scalar_one()
    linked_scan_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM scan_jobs WHERE review_id IS NOT NULL"
    )).scalar_one()
    linked_report_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM reports WHERE review_id IS NOT NULL"
    )).scalar_one()
    linked_finding_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM findings WHERE review_id IS NOT NULL"
    )).scalar_one()
    if (
        evidence_count
        or key_count
        or legacy_key_count
        or linked_scan_count
        or linked_report_count
        or linked_finding_count
    ):
        raise RuntimeError(
            "Cannot downgrade Computer Review evidence after it has been recorded; "
            "preserve or restore a database backup instead"
        )

    op.drop_index("ix_findings_scan_job_id", table_name="findings")
    op.drop_index("ix_findings_review_id", table_name="findings")
    op.drop_index("uq_agent_jobs_one_active_per_project", table_name="agent_jobs")
    op.drop_table("agent_job_idempotency_keys")

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
