"""qa_results confidence/evidence + repair_plans ladder columns

Revision ID: 10_qa_confidence_repair_ladder
Revises: 09_video_generations
Create Date: 2026-09-30

Week 3 Day 14 (AVOS-03 v1.1 s14, s15). qa_results and repair_plans were
scaffolded Day 2 (migration 02) but never written to. This extends both
to what the QA committee + repair ladder actually need:

  - qa_results.confidence / .evidence: the committee-level aggregate the
    Pydantic QAResult contract already had a field for.
  - repair_plans.shot_id / .attempt / .rung: the repair ladder's durable
    state. attempt is derived (count of existing rows for a shot + 1) at
    write time, not tracked anywhere else - these columns are what make
    that count cheap and what the QADashboard reads to show progression.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "10_qa_confidence_repair_ladder"
down_revision: Union[str, Sequence[str], None] = "09_video_generations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("qa_results", sa.Column("confidence", sa.Numeric(), nullable=True))
    op.add_column(
        "qa_results", sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="{}")
    )

    op.add_column("repair_plans", sa.Column("shot_id", sa.String(36), nullable=False, server_default=""))
    op.add_column("repair_plans", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("repair_plans", sa.Column("rung", sa.String(20), nullable=False, server_default="MICRO"))
    op.create_foreign_key(
        "fk_repair_plans_shot_id", "repair_plans", "shots", ["shot_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_repair_plans_shot_id", "repair_plans", ["shot_id"])
    # server_default was only to satisfy existing (in practice, zero) rows;
    # new rows always supply shot_id/attempt/rung explicitly.
    op.alter_column("repair_plans", "shot_id", server_default=None)
    op.alter_column("repair_plans", "attempt", server_default=None)
    op.alter_column("repair_plans", "rung", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_repair_plans_shot_id", table_name="repair_plans")
    op.drop_constraint("fk_repair_plans_shot_id", "repair_plans", type_="foreignkey")
    op.drop_column("repair_plans", "rung")
    op.drop_column("repair_plans", "attempt")
    op.drop_column("repair_plans", "shot_id")

    op.drop_column("qa_results", "evidence")
    op.drop_column("qa_results", "confidence")
