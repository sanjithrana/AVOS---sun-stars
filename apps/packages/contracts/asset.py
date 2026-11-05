from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssetLifecycleState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class Asset(BaseModel):
    """
    Canonical AVOS Asset contract.

    Assets are immutable, versioned, content-addressed,
    lifecycle-tracked, and lineage-linked.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    asset_id: UUID

    content_hash: str = Field(
        min_length=1,
    )

    asset_type: str = Field(
        min_length=1,
    )

    version: int = Field(
        ge=1,
    )

    created_by: UUID

    created_at: datetime

    source: str = Field(
        min_length=1,
    )

    parent_asset: UUID | None = None

    derived_assets: list[UUID] = Field(
        default_factory=list,
    )

    storage_uri: str = Field(
        min_length=1,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )

    lifecycle_state: AssetLifecycleState = (
        AssetLifecycleState.CREATED
    )
