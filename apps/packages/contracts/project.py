from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    name: str = Field(min_length=1, max_length=255)
    topic: str = Field(min_length=1)
    duration: int = Field(gt=0)
    aspect_ratio: str = Field(min_length=1)
    # Optional spend cap (Day 10). When set, BUDGET_WARNING fires at 80%
    # and BUDGET_EXCEEDED at 100% of audit-record costs.
    budget_limit: float | None = Field(default=None, gt=0)

    # Week 3 Day 16: per-project generation provider routing, set once
    # at creation from the New Project form's Text/Image/Video pickers.
    # None (the default, and every project created before this existed)
    # means "use the deployment default / auto-detect / mock" - see
    # agentic_core.models.{llm,image,video}.factory for exactly what
    # each name does and what env var it needs. Validated against those
    # factories' KNOWN_PROVIDERS in ProjectService, not here, so this
    # contract doesn't have to duplicate that list.
    llm_provider: str | None = None
    image_provider: str | None = None
    video_provider: str | None = None
    # Week 4: agentic_core.styles preset (None = "storybook").
    style_preset: str | None = None
    # Model Fabric: per-shot limits for this project (agentic_core.model_fabric.policy), validated in
    # ProjectService: preference, max_cost_per_shot, max_seconds_per_shot, max_attempts, quality_threshold,
    # allow_hosted, preferred_model, fallback_model. None = the Settings defaults.
    generation_policy: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        from_attributes=True,
    )

    id: str
    name: str
    topic: str
    duration_seconds: int
    aspect_ratio: str
    status: str
    budget_limit: float | None
    budget_spent: float
    llm_provider: str | None = None
    image_provider: str | None = None
    video_provider: str | None = None
    style_preset: str | None = None
    generation_policy: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
