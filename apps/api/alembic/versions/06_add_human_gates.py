"""add human_gates table

Revision ID: 06_add_human_gates
Revises: a51b0a758671
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "06_add_human_gates"
down_revision: Union[str, Sequence[str], None] = "a51b0a758671"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "human_gates",
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
            "gate_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "comment",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "decided_by",
            sa.String(255),
            nullable=True,
        ),
        sa.Column(
            "workflow_id",
            sa.String(255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_human_gates_project_id",
        "human_gates",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_human_gates_project_id",
        table_name="human_gates",
    )

    op.drop_table("human_gates")
