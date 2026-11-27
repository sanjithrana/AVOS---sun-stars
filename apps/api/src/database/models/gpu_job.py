"""gpu_jobs: one row per generation the Model Fabric ran (agentic_core.model_fabric.telemetry)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class GpuJob(Base):
    __tablename__ = "gpu_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    shot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    backend: Mapped[str] = mapped_column(String(20), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    worker_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gpu: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adapter: Mapped[str | None] = mapped_column(String(20), nullable=True)
    precision: Mapped[str | None] = mapped_column(String(10), nullable=True)
    attention: Mapped[str | None] = mapped_column(String(10), nullable=True)
    offload: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    where: Mapped[str] = mapped_column(String(120), nullable=False)
    units: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    step: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remote_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    est_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    est_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    gpu_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    wall_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    qa_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
