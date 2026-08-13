"""Add Evidence & Risk Gate columns (Post Cycle 8).

- finding_adjudications: created if missing (pre-existing migration/model
  drift — the alembic chain 001-003 never created this table, which the ORM
  bootstraps via Base.metadata.create_all at app startup), then deterministic
  policy-suppression audit columns are added.
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
    # ------------------------------------------------------------------
    # NOTE (Post Cycle 8 verification): the alembic chain (001-003) was
    # never kept in sync with the ORM models, which bootstrap tables via
    # Base.metadata.create_all at app startup. `finding_adjudications` was
    # therefore missing from migrations. Create it here (idempotent) so the
    # chain yields a complete, model-loadable schema, then add the gate
    # columns. This is a pre-existing migration/model-drift fix, not part of
    # the Evidence & Risk Gate feature surface.
    # ------------------------------------------------------------------
    op.create_table(
        "finding_adjudications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id")),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("scan_jobs.id")),
        sa.Column("trial_id", sa.String(100)),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("observation_status", sa.String(30)),
        sa.Column("concern_status", sa.String(30)),
        sa.Column("actionability_status", sa.String(30)),
        sa.Column("file_context", sa.String(30)),
        sa.Column("exceedance_ratio", sa.Float),
        sa.Column("operator", sa.String(255), nullable=False),
        sa.Column("operator_notes", sa.Text),
        sa.Column("reviewed_at", sa.DateTime, nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("confidence", sa.Float),
        sa.Column("evidence_snapshot", sa.JSON),
        sa.Column("governance_decision_at_review", sa.String(50)),
        sa.Column("related_mission_ids", sa.JSON),
        sa.Column("schema_version", sa.String(20)),
        sa.UniqueConstraint("finding_id", "operator", "reviewed_at",
                           name="uq_adjudication_per_operator_time"),
        if_not_exists=True,
    )
    op.create_index("ix_finding_adjudications_finding_id",
                    "finding_adjudications", ["finding_id"])
    op.create_index("ix_finding_adjudications_repository_id",
                    "finding_adjudications", ["repository_id"])
    op.create_index("ix_finding_adjudications_classification",
                    "finding_adjudications", ["classification"])

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
    op.add_column("findings", sa.Column("gate_state", sa.String(50), nullable=True))
    op.add_column("findings", sa.Column("risk_band", sa.String(20), nullable=True))
    op.add_column("findings", sa.Column("review_rank", sa.Float, nullable=True))
    op.add_column("findings", sa.Column("legacy_decision", sa.String(50), nullable=True))


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
