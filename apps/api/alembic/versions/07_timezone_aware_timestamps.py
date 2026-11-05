"""make projects/shots timestamps timezone-aware

Revision ID: 07_timezone_aware_timestamps
Revises: 06_add_human_gates
Create Date: 2026-09-27

projects.created_at/updated_at and shots.created_at/updated_at were
created as TIMESTAMP WITHOUT TIME ZONE while the ORM models declare
DateTime(timezone=True) and every newer table (jobs, audit_records,
human_gates) uses TIMESTAMPTZ. The mismatch made API responses mix
offset-less and 'Z' timestamps. Existing values are interpreted as UTC.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "07_timezone_aware_timestamps"
down_revision: Union[str, Sequence[str], None] = "06_add_human_gates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("projects", "created_at"),
    ("projects", "updated_at"),
    ("shots", "created_at"),
    ("shots", "updated_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE TIMESTAMP WITH TIME ZONE USING {column} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE TIMESTAMP WITHOUT TIME ZONE USING {column} AT TIME ZONE 'UTC'"
        )
