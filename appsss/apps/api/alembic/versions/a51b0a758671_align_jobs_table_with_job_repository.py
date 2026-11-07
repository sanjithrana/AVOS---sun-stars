"""align jobs table with job repository"""

from alembic import op
import sqlalchemy as sa


revision = "a51b0a758671"
down_revision = "05_update_projects_for_avos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing legacy columns → current JobRepository names.
    op.alter_column(
        "jobs",
        "type",
        new_column_name="job_type",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    op.alter_column(
        "jobs",
        "payload",
        new_column_name="input_payload",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )

    op.alter_column(
        "jobs",
        "error",
        new_column_name="error_message",
        existing_type=sa.Text(),
        existing_nullable=True,
    )

    # Existing jobs used uppercase PENDING.
    op.execute(
        """
        UPDATE jobs
        SET status = 'queued'
        WHERE status = 'PENDING'
        """
    )

    op.execute(
        """
        UPDATE jobs
        SET status = lower(status)
        """
    )

    op.alter_column(
        "jobs",
        "input_payload",
        existing_type=sa.JSON(),
        nullable=True,
    )

    op.add_column(
        "jobs",
        sa.Column(
            "output_payload",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "workflow_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "temporal_run_id",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "temporal_run_id")
    op.drop_column("jobs", "workflow_id")
    op.drop_column("jobs", "output_payload")

    op.alter_column(
        "jobs",
        "input_payload",
        new_column_name="payload",
        existing_type=sa.JSON(),
        nullable=False,
    )

    op.alter_column(
        "jobs",
        "error_message",
        new_column_name="error",
        existing_type=sa.Text(),
        nullable=True,
    )

    op.execute(
        """
        UPDATE jobs
        SET status = upper(status)
        """
    )

    op.alter_column(
        "jobs",
        "status",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    op.alter_column(
        "jobs",
        "job_type",
        new_column_name="type",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
