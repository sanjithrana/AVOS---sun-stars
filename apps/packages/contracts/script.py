from pydantic import BaseModel, ConfigDict, Field


class ScriptScene(BaseModel):
    """A single narrated beat/scene within a generated script."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    narration: str = Field(min_length=1)
    visual_description: str = Field(min_length=1)
    estimated_seconds: float = Field(gt=0)


class Script(BaseModel):
    """
    Canonical AVOS generated-script contract.

    Produced by the script generation pipeline (agentic_core.pipelines.script)
    and consumed by the script-approval human gate and, once approved, by
    the audio (TTS) pipeline.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    topic: str
    scenes: list[ScriptScene] = Field(min_length=1)
    total_estimated_seconds: float = Field(gt=0)
    model: str = Field(min_length=1)

    @property
    def full_narration(self) -> str:
        """All scene narration concatenated, in order — the text TTS reads."""
        return " ".join(scene.narration for scene in self.scenes)


class ScriptValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: str  # "error" | "warning"
    message: str
