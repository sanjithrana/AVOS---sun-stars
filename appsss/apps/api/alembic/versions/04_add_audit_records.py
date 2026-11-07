"""add audit records table

Revision ID: 04_add_audit_records
Revises: 03_add_jobs
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "04_add_audit_records"
down_revision: Union[str, Sequence[str], None] = "03_add_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "agent_decision",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "tool_name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "tool_call_input",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "tool_result",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "cost",
            sa.Numeric(),
            nullable=False,
        ),
        sa.Column(
            "model",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "input_hash",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "output_hash",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_audit_records_project_id",
        "audit_records",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_records_project_id",
        table_name="audit_records",
    )

    op.drop_table("audit_records")
