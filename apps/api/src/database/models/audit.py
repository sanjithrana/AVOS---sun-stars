from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    agent_decision: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    tool_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    tool_call_input: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    tool_result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cost: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    input_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    output_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
