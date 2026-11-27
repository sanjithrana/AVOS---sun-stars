from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, utcnow


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    content_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        index=True,
    )

    # AVOS-07 defines asset_type as an enum, but the documented
    # vocabulary is not exhaustive ("etc."). Keep this string-based
    # until the complete enum vocabulary is formally defined.
    asset_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    parent_asset: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.asset_id"),
        nullable=True,
    )

    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Python attribute is "asset_metadata" because "metadata" is
    # reserved by SQLAlchemy Declarative API.
    # Database column remains exactly "metadata" per AVOS-07.
    asset_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
