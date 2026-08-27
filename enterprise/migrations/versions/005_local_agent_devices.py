"""Add Local Agent device trust domain tables (LA1).

Creates:
- `devices` table: device identity, status, capabilities, and audit columns
- `bootstrap_tokens` table: hashed single-use bootstrap tokens for device registration

This migration extends 004_evidence_risk_gate.

Revision ID: 005_local_agent_devices
Revises: 004_evidence_risk_gate
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_local_agent_devices"
down_revision: Union[str, None] = "004_evidence_risk_gate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("device_name", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("capabilities", sa.JSON, nullable=True),
        sa.Column("registered_at", sa.DateTime, nullable=True),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "bootstrap_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("device_id", sa.String(128), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("consumed", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("bootstrap_tokens")
    op.drop_table("devices")
