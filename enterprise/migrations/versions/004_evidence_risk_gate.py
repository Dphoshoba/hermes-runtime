"""Add Evidence & Risk Gate columns (Post Cycle 8).

- finding_adjudications: deterministic policy-suppression audit columns.
- findings: gate routing columns (machine gate state, risk band, review
  rank, legacy decision). Historical rows are untouched; these are nullable.

Revision ID: 004_evidence_risk_gate
Revises: 003_scan_hardening
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_evidence_risk_gate"
down_revision: Union[str, None] = "003_scan_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deterministic policy suppression — auditable, distinct from human NOT_ACTIONABLE.
    op.add_column(
        "finding_adjudications",
        sa.Column("policy_suppressed", sa.Boolean, server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "finding_adjudications",
        sa.Column("suppression_rule_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "finding_adjudications",
        sa.Column("suppression_rule_version", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_finding_adjudications_policy_suppressed",
        "finding_adjudications", ["policy_suppressed"],
    )
    op.create_index(
        "ix_finding_adjudications_suppression_rule_id",
        "finding_adjudications", ["suppression_rule_id"],
    )

    # Evidence & Risk Gate routing on findings (machine authority).
    op.add_column(
        "findings",
        sa.Column("gate_state", sa.String(50), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("risk_band", sa.String(20), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("review_rank", sa.Float, nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("legacy_decision", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_finding_adjudications_suppression_rule_id", table_name="finding_adjudications")
    op.drop_index("ix_finding_adjudications_policy_suppressed", table_name="finding_adjudications")
    op.drop_column("finding_adjudications", "suppression_rule_version")
    op.drop_column("finding_adjudications", "suppression_rule_id")
    op.drop_column("finding_adjudications", "policy_suppressed")
    op.drop_column("findings", "legacy_decision")
    op.drop_column("findings", "review_rank")
    op.drop_column("findings", "risk_band")
    op.drop_column("findings", "gate_state")
