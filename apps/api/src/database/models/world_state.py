from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class WorldStateRecord(Base):
    """
    Versioned WorldState snapshots (AVOS-03 v1.1 s8). Version 0 is the
    initial world; each accepted shot appends version+1 with
    source_shot_id pointing at the shot that caused it.
    """

    __tablename__ = "world_states"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_world_states_project_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_shot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shots.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
