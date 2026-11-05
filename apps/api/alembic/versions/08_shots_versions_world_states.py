"""shots (reshaped), shot_versions, world_states

Revision ID: 08_shots_versions_world_states
Revises: 07_timezone_aware_timestamps
Create Date: 2026-09-28

Week 3 Day 11 (AVOS-07 s3.3-3.4, AVOS-03 v1.1 s8).

The Week 1 `shots` table was a placeholder (name/description/shot_spec_id)
that nothing ever wrote to. It is altered in place - not dropped - because
qa_results.shot_id has a foreign key to shots.id.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "08_shots_versions_world_states"
down_revision: Union[str, Sequence[str], None] = "07_timezone_aware_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- shots: placeholder columns out, shot-list columns in ------------
    op.drop_index("ix_shots_shot_spec_id", table_name="shots")
    op.drop_column("shots", "shot_spec_id")
    op.drop_column("shots", "name")
    op.drop_column("shots", "description")

    op.add_column("shots", sa.Column("shot_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("shots", sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("shots", sa.Column("beat_label", sa.String(100), nullable=False, server_default=""))
    op.add_column("shots", sa.Column("start_time", sa.Float(), nullable=False, server_default="0"))
    op.add_column("shots", sa.Column("end_time", sa.Float(), nullable=False, server_default="0"))
    op.alter_column("shots", "status", server_default="DRAFT")
    op.create_unique_constraint("uq_shots_project_index", "shots", ["project_id", "shot_index"])

    # -- shot_versions: immutable versioned ShotSpecs --------------------
    op.create_table(
        "shot_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("shot_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("continuity", postgresql.JSONB(), nullable=True),
        sa.Column("physics_proxy_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shot_id"], ["shots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["physics_proxy_asset_id"], ["assets.asset_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shot_id", "version", name="uq_shot_versions_shot_version"),
    )
    op.create_index("ix_shot_versions_shot_id", "shot_versions", ["shot_id"])

    # -- world_states: versioned continuity snapshots --------------------
    op.create_table(
        "world_states",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("source_shot_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_shot_id"], ["shots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_world_states_project_version"),
    )
    op.create_index("ix_world_states_project_id", "world_states", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_world_states_project_id", table_name="world_states")
    op.drop_table("world_states")
    op.drop_index("ix_shot_versions_shot_id", table_name="shot_versions")
    op.drop_table("shot_versions")

    op.drop_constraint("uq_shots_project_index", "shots", type_="unique")
    for column in ("end_time", "start_time", "beat_label", "current_version", "shot_index"):
        op.drop_column("shots", column)
    op.add_column("shots", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("shots", sa.Column("name", sa.String(255), nullable=False, server_default=""))
    op.add_column("shots", sa.Column("shot_spec_id", sa.String(36), nullable=True))
    op.create_index("ix_shots_shot_spec_id", "shots", ["shot_spec_id"])
