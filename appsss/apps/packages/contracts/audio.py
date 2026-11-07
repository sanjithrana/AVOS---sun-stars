from pydantic import BaseModel, ConfigDict, Field


class WordTimestamp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class SentenceTimestamp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    word_count: int = Field(ge=0)


class SemanticBeat(BaseModel):
    """A marked point in the narration where the visual should change."""

    model_config = ConfigDict(extra="forbid")

    time: float = Field(ge=0)
    label: str


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    words: list[WordTimestamp] = Field(default_factory=list)
    duration_seconds: float = Field(ge=0)


class AudioSynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_hash: str
    format: str
    duration_seconds: float = Field(ge=0)
    size_bytes: int = Field(ge=0)
