"""projects: llm/image/video provider selection

Revision ID: 11_generation_provider_selection
Revises: 10_qa_confidence_repair_ladder
Create Date: 2026-09-27

Week 3 Day 16 (per-project generation provider routing). Adds three
nullable columns so a project can pin which LLM/image/video provider it
was created with (agentic_core.models.{llm,image,video}.factory read
these). NULL on every existing row - unchanged auto-detect/mock
behaviour for anything created before this.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "11_generation_provider_selection"
down_revision: str | Sequence[str] | None = "10_qa_confidence_repair_ladder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("llm_provider", sa.String(length=50), nullable=True))
    op.add_column("projects", sa.Column("image_provider", sa.String(length=50), nullable=True))
    op.add_column("projects", sa.Column("video_provider", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "video_provider")
    op.drop_column("projects", "image_provider")
    op.drop_column("projects", "llm_provider")
