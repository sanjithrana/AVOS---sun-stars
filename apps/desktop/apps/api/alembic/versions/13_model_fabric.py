"""Model Fabric: gpu_jobs + projects.generation_policy

Revision ID: 13_model_fabric
Revises: 12_project_style_preset
Create Date: 2026-10-03

Every generation the Model Fabric runs (on a GPU worker, your ComfyUI server, Cloudflare or fal.ai) gets one
gpu_jobs row: where it ran, at which precision, how long it took, what it cost, and later the QA score of its
result. The rows drive the GPU page and the router's learned performance. A project's generation_policy holds its
per-shot limits (NULL = the Settings defaults), so existing projects are unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "13_model_fabric"
down_revision: str | Sequence[str] | None = "12_project_style_preset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("generation_policy", postgresql.JSONB(), nullable=True))
    op.create_table(
        "gpu_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("shot_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("task", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("backend", sa.String(length=20), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("worker_name", sa.String(length=120), nullable=True),
        sa.Column("gpu", sa.String(length=120), nullable=True),
        sa.Column("adapter", sa.String(length=20), nullable=True),
        sa.Column("precision", sa.String(length=10), nullable=True),
        sa.Column("attention", sa.String(length=10), nullable=True),
        sa.Column("offload", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("where", sa.String(length=120), nullable=False),
        sa.Column("units", sa.Float(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("step", sa.String(length=200), nullable=True),
        sa.Column("remote_id", sa.String(length=64), nullable=True),
        sa.Column("est_seconds", sa.Float(), nullable=True),
        sa.Column("est_cost", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reasons", postgresql.JSONB(), nullable=True),
        sa.Column("gpu_seconds", sa.Float(), nullable=True),
        sa.Column("wall_seconds", sa.Float(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("qa_score", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_gpu_jobs_project", "gpu_jobs", ["project_id", "created_at"])
    op.create_index("ix_gpu_jobs_shot", "gpu_jobs", ["shot_id", "version"])
    op.create_index("ix_gpu_jobs_model_where", "gpu_jobs", ["model", "where"])


def downgrade() -> None:
    op.drop_index("ix_gpu_jobs_model_where", table_name="gpu_jobs")
    op.drop_index("ix_gpu_jobs_shot", table_name="gpu_jobs")
    op.drop_index("ix_gpu_jobs_project", table_name="gpu_jobs")
    op.drop_table("gpu_jobs")
    op.drop_column("projects", "generation_policy")
