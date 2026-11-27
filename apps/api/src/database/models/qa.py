from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class QACommitteeVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class QAResult(Base):
    __tablename__ = "qa_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    shot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shots.id"),
        nullable=False,
        index=True,
    )

    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.asset_id"),
        nullable=False,
    )

    visual_score: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    visual_pass: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    temporal_score: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    temporal_pass: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    geometry_score: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    geometry_pass: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    identity_score: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    identity_pass: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    audio_score: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    audio_pass: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    prompt_adherence_score: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    prompt_pass: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    committee_verdict: Mapped[QACommitteeVerdict] = mapped_column(
        SAEnum(
            QACommitteeVerdict,
            name="qa_committee_verdict",
        ),
        nullable=False,
    )

    diagnostics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Week 3 Day 14 (AVOS-03 v1.1 s15): the committee-level aggregate the
    # Pydantic QAResult contract already carried (packages/contracts/qa.py)
    # but this table had no columns for yet.
    confidence: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    evidence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
