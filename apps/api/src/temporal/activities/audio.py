from dataclasses import dataclass
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.services.audio_service import AudioService, GateNotApprovedError
from src.services.director_service import DirectorStoppedError
from src.temporal.activities._session import activity_session


@dataclass
class AudioInput:
    project_id: str
    gate_id: str


@activity.defn
async def generate_audio_activity(inp: AudioInput) -> dict[str, Any]:
    """Thin Temporal wrapper (Day 8): no TTS logic here - the pipeline
    lives in agentic_core, orchestration in AudioService."""
    async with activity_session() as session:
        try:
            return await AudioService(session).generate_for_gate(inp.project_id, inp.gate_id)
        except (GateNotApprovedError, DirectorStoppedError) as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
