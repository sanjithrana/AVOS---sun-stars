from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    PROJECT_CREATED = "PROJECT_CREATED"
    SCRIPT_GENERATED = "SCRIPT_GENERATED"
    SCRIPT_APPROVED = "SCRIPT_APPROVED"

    AUDIO_GENERATED = "AUDIO_GENERATED"
    SHOT_CREATED = "SHOT_CREATED"
    BLENDER_RENDERED = "BLENDER_RENDERED"
    VIDEO_GENERATED = "VIDEO_GENERATED"

    QA_FAILED = "QA_FAILED"
    QA_PASSED = "QA_PASSED"

    REPAIR_STARTED = "REPAIR_STARTED"
    REPAIR_ESCALATED = "REPAIR_ESCALATED"
    SHOT_APPROVED = "SHOT_APPROVED"

    VIDEO_ASSEMBLED = "VIDEO_ASSEMBLED"
    FINAL_QA_PASSED = "FINAL_QA_PASSED"
    VIDEO_PUBLISHED = "VIDEO_PUBLISHED"

    ANALYTICS_RECEIVED = "ANALYTICS_RECEIVED"
    EXPERIENCE_RECORDED = "EXPERIENCE_RECORDED"

    POLICY_CANDIDATE_CREATED = "POLICY_CANDIDATE_CREATED"
    POLICY_SHADOWED = "POLICY_SHADOWED"
    POLICY_ACTIVATED = "POLICY_ACTIVATED"
    POLICY_DEPRECATED = "POLICY_DEPRECATED"

    BUDGET_WARNING = "BUDGET_WARNING"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

    HUMAN_OVERRIDE_APPLIED = "HUMAN_OVERRIDE_APPLIED"
    HUMAN_GATE_OPENED = "HUMAN_GATE_OPENED"
    HUMAN_GATE_DECIDED = "HUMAN_GATE_DECIDED"

    # Week 2 live-UI events (replace client polling with SSE):
    # every audit_records row -> AGENT_ACTION_RECORDED (Day 9),
    # job/project lifecycle transitions -> *_STATUS_CHANGED.
    AGENT_ACTION_RECORDED = "AGENT_ACTION_RECORDED"
    JOB_STATUS_CHANGED = "JOB_STATUS_CHANGED"
    PROJECT_STATUS_CHANGED = "PROJECT_STATUS_CHANGED"

    # Week 3
    CONTINUITY_CHECKED = "CONTINUITY_CHECKED"

    # Model Fabric: every generation run (GPU worker, ComfyUI, Cloudflare, fal.ai) - gpu_jobs rows
    GPU_JOB_QUEUED = "GPU_JOB_QUEUED"
    GPU_JOB_STARTED = "GPU_JOB_STARTED"
    GPU_JOB_PROGRESS = "GPU_JOB_PROGRESS"
    GPU_JOB_COMPLETED = "GPU_JOB_COMPLETED"
    GPU_JOB_FAILED = "GPU_JOB_FAILED"


class Event(BaseModel):
    """
    Canonical AVOS Event envelope.

    Events are published to the Event Bus for cross-subsystem fan-out.
    Temporal remains responsible for durable workflow execution.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: str = Field(
        min_length=1,
    )

    event_type: EventType

    timestamp: datetime

    organization_id: str = Field(
        min_length=1,
    )

    project_id: str | None = None

    correlation_id: str = Field(
        min_length=1,
    )

    causation_id: str | None = None

    payload: dict[str, Any] = Field(
        default_factory=dict,
    )
