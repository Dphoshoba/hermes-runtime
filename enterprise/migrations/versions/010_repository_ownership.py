"""Add owner identity to repositories.

Revision ID: 010_repository_ownership
Revises: 009_computer_review_evidence
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_repository_ownership"
down_revision: Union[str, None] = "009_computer_review_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_repositories_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
        )
        batch_op.create_index("ix_repositories_owner_user_id", ["owner_user_id"])


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
            "Cannot downgrade Computer Review evidence before dropping repository "
            "ownership; preserve or restore a database backup instead"
        )

    owned_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM repositories WHERE owner_user_id IS NOT NULL"
    )).scalar_one()
    if owned_count:
        raise RuntimeError(
            "Cannot downgrade repository ownership while repositories are assigned "
            "to users; preserve or restore a database backup instead"
        )

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_index("ix_repositories_owner_user_id")
        batch_op.drop_constraint(
            "fk_repositories_owner_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("owner_user_id")
