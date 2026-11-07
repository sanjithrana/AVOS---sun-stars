"""video_generations + shot_versions.video_generation_asset_id

Revision ID: 09_video_generations
Revises: 08_shots_versions_world_states
Create Date: 2026-09-29

Week 3 Day 13 (AVOS-03 v1.1 s9.5, s10). One row per video-generation
attempt for a ShotSpec version, keyed uniquely by idempotency_key so a
repeated dispatch of generate_video_shot is a lookup, not a new job.
shot_versions gets a pointer to the (first) attempt's root asset, mirroring
physics_proxy_asset_id from Day 12.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "09_video_generations"
down_revision: Union[str, Sequence[str], None] = "08_shots_versions_world_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shot_versions",
        sa.Column("video_generation_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shot_versions_video_generation_asset_id",
        "shot_versions",
        "assets",
        ["video_generation_asset_id"],
        ["asset_id"],
    )

    op.create_table(
        "video_generations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("shot_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="COMPLETED"),
        sa.Column("compiled_prompt", postgresql.JSONB(), nullable=False),
        sa.Column("candidates", postgresql.JSONB(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shot_id"], ["shots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_video_generations_idempotency_key"),
    )
    op.create_index("ix_video_generations_shot_id", "video_generations", ["shot_id"])
    op.create_index(
        "ix_video_generations_idempotency_key", "video_generations", ["idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_video_generations_idempotency_key", table_name="video_generations")
    op.drop_index("ix_video_generations_shot_id", table_name="video_generations")
    op.drop_table("video_generations")

    op.drop_constraint("fk_shot_versions_video_generation_asset_id", "shot_versions", type_="foreignkey")
    op.drop_column("shot_versions", "video_generation_asset_id")
