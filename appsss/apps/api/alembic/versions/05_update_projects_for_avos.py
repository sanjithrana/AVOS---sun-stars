"""Update projects table for AVOS project creation."""

from alembic import op
import sqlalchemy as sa


revision = "05_update_projects_for_avos"
down_revision = "04_add_audit_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "organization_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )

    op.alter_column(
        "projects",
        "channel_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )

    op.add_column(
        "projects",
        sa.Column("topic", sa.Text(), nullable=True),
    )

    op.add_column(
        "projects",
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )

    op.add_column(
        "projects",
        sa.Column("aspect_ratio", sa.String(length=20), nullable=True),
    )

    op.add_column(
        "projects",
        sa.Column("budget_limit", sa.Numeric(), nullable=True),
    )

    op.add_column(
        "projects",
        sa.Column("budget_spent", sa.Numeric(), nullable=True),
    )

    op.execute(
        """
        UPDATE projects
        SET
            topic = COALESCE(topic, name),
            duration_seconds = COALESCE(duration_seconds, 1),
            aspect_ratio = COALESCE(aspect_ratio, '9:16'),
            budget_spent = COALESCE(budget_spent, 0)
        """
    )

    op.alter_column(
        "projects",
        "topic",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.alter_column(
        "projects",
        "duration_seconds",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "projects",
        "aspect_ratio",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.alter_column(
        "projects",
        "budget_spent",
        existing_type=sa.Numeric(),
        nullable=False,
        server_default="0",
    )


def downgrade() -> None:
    op.drop_column("projects", "budget_spent")
    op.drop_column("projects", "budget_limit")
    op.drop_column("projects", "aspect_ratio")
    op.drop_column("projects", "duration_seconds")
    op.drop_column("projects", "topic")

    op.alter_column(
        "projects",
        "organization_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )

    op.alter_column(
        "projects",
        "channel_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
