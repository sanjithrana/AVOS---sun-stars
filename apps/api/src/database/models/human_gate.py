from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class HumanGate(Base):
    __tablename__ = "human_gates"

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

    gate_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    # Holds the artifact under review (e.g. the generated Script, as
    # dumped JSON) so the UI can render it without a second fetch.
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    decided_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Set when a Temporal workflow is paused awaiting this gate, so the
    # approval endpoint knows which workflow to signal on decision.
    workflow_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
