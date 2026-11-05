"""projects: style preset

Revision ID: 12_project_style_preset
Revises: 11_generation_provider_selection
Create Date: 2026-10-02

Week 4: a project's style preset (agentic_core.styles) - script tone,
visual look, music mood and caption size. NULL = the original
"storybook" style, so existing projects are unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "12_project_style_preset"
down_revision: str | Sequence[str] | None = "11_generation_provider_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("style_preset", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "style_preset")
