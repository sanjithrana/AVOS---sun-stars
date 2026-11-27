from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class VideoGeneration(Base):
    """
    Week 3 Day 13 - one video-generation attempt for a ShotSpec version.

    idempotency_key is unique: a second dispatch of generate_video_shot
    with the same key (caller-supplied, or the executor's own default of
    shot_id+version+content_hash+physics_proxy_asset_id) finds this row
    and returns it unchanged instead of generating new candidates or
    rows (AVOS-03 v1.1 s9.5).
    """

    __tablename__ = "video_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    shot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")

    # CompiledPrompt of candidate 0, kept for audit/debugging; every
    # candidate's own compiled params are on its own asset's metadata.
    compiled_prompt: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # [{"index": 0, "asset_id": "...", "thumbnail_asset_id": "...", "seed": N, "params_hash": "..."}, ...]
    candidates: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Root "video_generation" asset (descriptor + lineage parent of the
    # per-candidate assets), mirroring the Blender physics_proxy pattern.
    asset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=False)

    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
