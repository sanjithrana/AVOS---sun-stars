"""Request/response shapes for the shots API (Week 3)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.contracts.common import UUIDStr
from packages.contracts.shotspec import ContinuityReport, ShotContent


class CreateShotSpecRequest(BaseModel):
    """POST /projects/{id}/shots - new shot, or new version if a shot
    already exists at shot_index."""

    model_config = ConfigDict(extra="forbid")

    content: ShotContent
    shot_index: int | None = Field(default=None, ge=0)


class ShotAssetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUIDStr
    asset_type: str
    content_hash: str
    parent_asset: UUIDStr | None = None
    metadata: dict = Field(default_factory=dict)


class VideoCandidateResponse(BaseModel):
    """One of the 3 generated candidates (AVOS-08 s8.3) for a ShotSpec
    version - Week 3 Day 13."""

    model_config = ConfigDict(extra="forbid")

    index: int
    asset_id: UUIDStr
    thumbnail_asset_id: UUIDStr
    # Week 3 Day 16: set only when a project's video_provider actually
    # rendered a real clip for this candidate (self-hosted only - see
    # agentic_core.models.video.factory). None in every existing/mock
    # generation, same as before this field existed.
    render_asset_id: UUIDStr | None = None
    seed: int
    params_hash: str


class VideoGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_generation_id: str
    idempotency_key: str
    status: str
    cached: bool = False
    candidates: list[VideoCandidateResponse] = Field(default_factory=list)


class ShotVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shotspec_id: str
    version: int
    parent_version: int | None
    status: str
    content: ShotContent
    content_hash: str
    created_by: str
    created_at: datetime
    continuity: ContinuityReport | None = None
    physics_proxy_asset_id: UUIDStr | None = None
    video_generation_asset_id: UUIDStr | None = None
    video_generation: VideoGenerationResponse | None = None


class ShotResponse(BaseModel):
    """A shot with its *current* version inlined (Storyboard rows)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    shot_index: int
    status: str
    current_version: int
    beat_label: str
    start_time: float
    end_time: float
    created_at: datetime
    updated_at: datetime
    spec: ShotVersionResponse


class ShotDetailResponse(ShotResponse):
    """GET /shots/{id}: every version + Blender-stage assets (Day 12)."""

    versions: list[ShotVersionResponse] = Field(default_factory=list)
    physics_assets: list[ShotAssetResponse] = Field(default_factory=list)
