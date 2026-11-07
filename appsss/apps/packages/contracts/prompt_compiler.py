"""
Compiled generation parameters (Week 3 Day 13, Engineer 2).

The Prompt Compiler (agentic_core/pipelines/shot/prompt_compiler.py) turns
a ShotSpec's ShotContent into this contract. It must be deterministic:
the same ShotContent + physics_proxy_asset_id + candidate_index always
compiles to the same CompiledPrompt (asserted by
agentic_core/tests/test_prompt_compiler.py). params_hash is the
sha256 of the compiled fields (everything but itself) and is what the
idempotency-key default (AVOS-03 v1.1 s9.5) is derived from downstream.
"""

from pydantic import BaseModel, ConfigDict, Field


class CompiledPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=1)
    negative_prompt: str = ""

    seed: int
    candidate_index: int = Field(ge=0)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)

    camera_movement: str
    lens_mm: int
    style: str | None = None

    physics_proxy_asset_id: str
    conditioning_passes: list[str] = Field(default_factory=list)

    params_hash: str = Field(min_length=1)
