"""
Gateway declarations for the Week 3 shot tools.

agentic_core owns *what* the tools are (name, input schema, permission,
timeout). Their executors live in the api layer
(src/services/shotspec_service.py) because they read/write the shots,
shot_versions and world_states tables - Engineer 1's execution side.
"""

from pydantic import BaseModel, ConfigDict, Field

from tool_gateway.schemas import ToolSchema


class CreateShotSpecInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    content: dict  # ShotContent JSON; validated again by the executor
    shot_index: int | None = Field(default=None, ge=0)


class ValidateShotSpecInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    version: int | None = Field(default=None, ge=1)
    advance_world_state: bool = True


class GetWorldStateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str


CREATE_SHOT_SPEC = ToolSchema(
    name="create_shot_spec",
    description="Persist a ShotSpec (new shot, or a new version of an existing shot).",
    schema=CreateShotSpecInput.model_json_schema(),
    permission="planning",
    timeout=30,
)

VALIDATE_SHOT_SPEC = ToolSchema(
    name="validate_shot_spec",
    description="Check a ShotSpec's continuity against the WorldState before it.",
    schema=ValidateShotSpecInput.model_json_schema(),
    permission="planning",
    timeout=30,
)

GET_WORLD_STATE = ToolSchema(
    name="get_world_state",
    description="Read the project's current WorldState.",
    schema=GetWorldStateInput.model_json_schema(),
    permission="memory",
    timeout=10,
)


# -- Week 3 Day 12: physics-before-pixels --------------------------------------


class RunBlenderProxyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    version: int | None = Field(default=None, ge=1)


class GenerateVideoShotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    # Optional in the *schema* on purpose: omitting it must surface as the
    # constitution's MISSING_DEPENDENCY, not a generic schema error.
    physics_proxy_asset_id: str | None = None
    prompt: str | None = None
    # Week 3 Day 13 (AVOS-03 v1.1 s9.5): a caller-supplied idempotency key.
    # Firing the same call twice with the same key returns the first
    # call's job/candidates instead of generating again. If omitted, the
    # executor derives one from (shot_id, version, content_hash,
    # physics_proxy_asset_id) so an accidental double-submit is still
    # deduplicated.
    idempotency_key: str | None = None


RUN_BLENDER_PROXY = ToolSchema(
    name="run_blender_proxy",
    description="Blender stage: render a ShotSpec's physics proxy (depth/normal/canny/mask).",
    schema=RunBlenderProxyInput.model_json_schema(),
    permission="blender",
    timeout=300,
)

GENERATE_VIDEO_SHOT = ToolSchema(
    name="generate_video_shot",
    description="Generate a video shot conditioned on its Blender physics proxy.",
    schema=GenerateVideoShotInput.model_json_schema(),
    permission="comfyui",
    # Hosted AI clips take minutes; a local GPU (ComfyUI) can take longer.
    timeout=1800,
)


class AssembleVideoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    audio_asset_id: str


ASSEMBLE_VIDEO = ToolSchema(
    name="assemble_video",
    description="Render the final video: every shot's clip/image in timeline order + narration + captions.",
    schema=AssembleVideoInput.model_json_schema(),
    permission="comfyui",
    timeout=1800,
)
