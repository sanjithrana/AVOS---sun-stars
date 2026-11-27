from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class Shot(Base):
    """
    One shot in a project's shot list (AVOS-07 s3.3).

    The row is the stable identity + current pointer; every edit is a new
    immutable row in shot_versions (the versioned ShotSpec). `id` stays a
    string UUID because qa_results.shot_id already references it.
    """

    __tablename__ = "shots"
    __table_args__ = (UniqueConstraint("project_id", "shot_index", name="uq_shots_project_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )

    shot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Mirrors the current version's ShotSpecStatus (DRAFT, PLANNED, ...).
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")

    beat_label: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    start_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    end_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
