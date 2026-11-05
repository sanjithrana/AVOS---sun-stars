from pydantic import BaseModel, ConfigDict, Field

from tool_gateway.schemas import ToolSchema


class GenerateAudioInput(BaseModel):
    """Input for the audio-first pipeline (TTS -> Whisper -> beats)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    gate_id: str
    narration: str = Field(min_length=1)


class GenerateAudioTool:
    """
    Tool Gateway declaration for audio generation.

    Only the schema/permission lives here (agentic_core owns *what* the
    tool is). The executor is supplied by the api layer's AudioService,
    because it must also persist the audio bytes through the Asset
    Registry - storage is Engineer 1's execution layer, not agent logic.
    """

    schema = ToolSchema(
        name="generate_audio",
        description=(
            "Synthesize narration for an approved script and extract word "
            "timestamps, sentence timestamps and semantic beats."
        ),
        schema=GenerateAudioInput.model_json_schema(),
        permission="audio",
        timeout=300,
    )
