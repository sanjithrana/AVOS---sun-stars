from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    topic: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    aspect_ratio: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="planning",
    )

    budget_limit: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    budget_spent: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
        default=0,
    )

    # Week 3 Day 16: per-project generation provider routing (the New
    # Project form's Text/Image/Video pickers -
    # agentic_core.models.{llm,image,video}.factory). None means "use
    # the deployment default / auto-detect / mock", exactly matching
    # every project created before this existed.
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    video_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Week 4: agentic_core.styles preset; None = "storybook".
    style_preset: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Model Fabric: this project's per-shot limits (preference, max cost/time, attempts, QA bar); None = Settings defaults.
    generation_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
