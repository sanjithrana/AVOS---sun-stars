"""add assets qa results and repair plans

Revision ID: 02_add_assets_qa_repairs
Revises: 48cef4921846
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "02_add_assets_qa_repairs"
down_revision: Union[str, Sequence[str], None] = "48cef4921846"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # ASSETS
    # AVOS-07 §3.5
    # ---------------------------------------------------------
    op.create_table(
        "assets",
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "asset_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "parent_asset",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "storage_path",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_asset"],
            ["assets.asset_id"],
        ),
        sa.PrimaryKeyConstraint("asset_id"),
    )

    op.create_index(
        "ix_assets_content_hash",
        "assets",
        ["content_hash"],
        unique=True,
    )

    # ---------------------------------------------------------
    # QA RESULTS
    # AVOS-07 §3.6
    # ---------------------------------------------------------
    qa_committee_verdict = postgresql.ENUM(
        "PASS",
        "FAIL",
        name="qa_committee_verdict",
        create_type=False,
    )

    qa_committee_verdict.create(
        op.get_bind(),
        checkfirst=True,
    )

    op.create_table(
        "qa_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "shot_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "visual_score",
            sa.Numeric(),
            nullable=True,
        ),
        sa.Column(
            "visual_pass",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "temporal_score",
            sa.Numeric(),
            nullable=True,
        ),
        sa.Column(
            "temporal_pass",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "geometry_score",
            sa.Numeric(),
            nullable=True,
        ),
        sa.Column(
            "geometry_pass",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "identity_score",
            sa.Numeric(),
            nullable=True,
        ),
        sa.Column(
            "identity_pass",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "audio_score",
            sa.Numeric(),
            nullable=True,
        ),
        sa.Column(
            "audio_pass",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "prompt_adherence_score",
            sa.Numeric(),
            nullable=True,
        ),
        sa.Column(
            "prompt_pass",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "committee_verdict",
            qa_committee_verdict,
            nullable=False,
        ),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["shot_id"],
            ["shots.id"],
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_qa_results_shot_id",
        "qa_results",
        ["shot_id"],
        unique=False,
    )

    # ---------------------------------------------------------
    # REPAIR PLANS
    # AVOS-07 §3.7
    # ---------------------------------------------------------
    op.create_table(
        "repair_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "qa_result_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "failure_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "target_stage",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "changes",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "preserve",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resulting_asset_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "resulting_qa_result_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["qa_result_id"],
            ["qa_results.id"],
        ),
        sa.ForeignKeyConstraint(
            ["resulting_asset_id"],
            ["assets.asset_id"],
        ),
        sa.ForeignKeyConstraint(
            ["resulting_qa_result_id"],
            ["qa_results.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_repair_plans_qa_result_id",
        "repair_plans",
        ["qa_result_id"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse dependency order.

    op.drop_index(
        "ix_repair_plans_qa_result_id",
        table_name="repair_plans",
    )

    op.drop_table("repair_plans")

    op.drop_index(
        "ix_qa_results_shot_id",
        table_name="qa_results",
    )

    op.drop_table("qa_results")

    # The enum is owned by the migration, so remove it after
    # qa_results has been dropped.
    qa_committee_verdict = postgresql.ENUM(
        "PASS",
        "FAIL",
        name="qa_committee_verdict",
        create_type=False,
    )

    qa_committee_verdict.drop(
        op.get_bind(),
        checkfirst=True,
    )

    op.drop_index(
        "ix_assets_content_hash",
        table_name="assets",
    )

    op.drop_table("assets")
