from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class ShotVersion(Base):
    """
    Immutable, versioned ShotSpec (AVOS-03 v1.1 s8, AVOS-07 s3.3).

    id == ShotSpec.shotspec_id. (shot_id, version) is unique; version N+1
    records parent_version=N. `content` is the ShotContent JSON and
    `content_hash` its SHA-256, so identical content is detectable.
    """

    __tablename__ = "shot_versions"
    __table_args__ = (UniqueConstraint("shot_id", "version", name="uq_shot_versions_shot_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    shot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shots.id", ondelete="CASCADE"), nullable=False, index=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")

    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    # Last continuity report for this version (ContinuityReport JSON).
    continuity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Physics-before-pixels (Day 12): set when the Blender stage has
    # produced this version's physics proxy. Generation is refused until
    # it exists.
    physics_proxy_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=True
    )

    # Week 3 Day 13: the video_generation_id root asset once this version's
    # candidates have been generated (see VideoGenerationService). None
    # until then; status moves BLENDER_READY -> QA_PENDING at the same
    # time this is set.
    video_generation_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
