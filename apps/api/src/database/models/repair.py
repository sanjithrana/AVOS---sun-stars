from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class RepairPlan(Base):
    __tablename__ = "repair_plans"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    qa_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("qa_results.id"),
        nullable=False,
        index=True,
    )

    # Week 3 Day 14: denormalized for the ladder itself. shot_id makes
    # "how many repair attempts has this shot had" a plain count query
    # (services/repair_service.py) rather than a join through qa_results
    # every time - and that count *is* the durable attempt counter: it
    # survives a worker restart for free, because it's just existing
    # committed rows, never anything held in process memory.
    shot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    rung: Mapped[str] = mapped_column(String(20), nullable=False)

    failure_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    target_stage: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    changes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    preserve: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resulting_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.asset_id"),
        nullable=True,
    )

    resulting_qa_result_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("qa_results.id"),
        nullable=True,
    )
