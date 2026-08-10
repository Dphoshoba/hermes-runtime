"""Initial schema — all tables for Engineering Command Center v1.0

Revision ID: 001_initial
Revises: None
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_admin", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # Repositories
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("default_branch", sa.String(255), default="main"),
        sa.Column("language", sa.String(100)),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("last_scanned_at", sa.DateTime),
        sa.Column("health_score", sa.Float),
        sa.Column("findings_count", sa.Integer, default=0),
        sa.Column("metadata_json", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # Journal Events
    op.create_table(
        "journal_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("timestamp", sa.String(30), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("stage", sa.String(100), nullable=False, index=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), index=True),
        sa.Column("actor", sa.String(255), default="system"),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime),
    )

    # Findings
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), index=True),
        sa.Column("finding_type", sa.String(100), nullable=False, index=True),
        sa.Column("severity", sa.String(50), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("module", sa.String(512)),
        sa.Column("priority_score", sa.Float),
        sa.Column("effort", sa.String(50)),
        sa.Column("status", sa.String(50), default="open", index=True),
        sa.Column("metadata_json", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # Missions
    op.create_table(
        "missions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("mission_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), default="pending", index=True),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("configuration", sa.JSON, default=dict),
        sa.Column("created_by", sa.String(255)),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("error_message", sa.Text),
        sa.Column("metadata_json", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # Reports
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(36), sa.ForeignKey("missions.id"), index=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("report_data", sa.JSON, nullable=False),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("tasks_planned", sa.Integer),
        sa.Column("tasks_completed", sa.Integer),
        sa.Column("tasks_failed", sa.Integer),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("missions")
    op.drop_table("findings")
    op.drop_table("journal_events")
    op.drop_table("repositories")
    op.drop_table("users")
