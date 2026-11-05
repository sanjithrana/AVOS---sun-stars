from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.director.director import PipelineState
from agentic_core.pipelines.audio.semantic_beats import extract_semantic_beats
from agentic_core.pipelines.audio.timestamps import extract_sentence_timestamps
from agentic_core.pipelines.audio.tts import get_tts_provider
from agentic_core.pipelines.audio.whisper import get_whisper_provider
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.audio import TranscriptionResult
from packages.contracts.event import EventType
from packages.contracts.human_gate import HumanGateStatus
from packages.contracts.script import Script
from src.core.assets.registry import AssetRegistry
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, queue_event
from src.domain.projects.status import ProjectStatus
from src.repositories.human_gate_repository import HumanGateRepository
from src.services.director_service import DirectorService
from src.services.gateway_bridge import dispatch_and_audit


class GateNotApprovedError(RuntimeError):
    """Audio was requested for a script that isn't approved."""


def script_from_gate_payload(payload: dict[str, Any]) -> Script:
    """The gate payload is the Script plus review-only extras (e.g.
    validation_issues); Script is extra='forbid', so strip them."""
    fields = set(Script.model_fields)
    return Script.model_validate({k: v for k, v in payload.items() if k in fields})


class AudioService:
    """
    Day 8/9 audio-first pipeline for an *approved* script:
        narration -> TTS -> Whisper -> sentence timestamps -> semantic beats
        -> content-addressed audio asset -> AUDIO_GENERATED

    Pipeline logic lives in agentic_core (Engineer 2). This service is
    the execution side (Engineer 1): it supplies the Gateway executor
    that also persists the bytes through the Asset Registry.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gates = HumanGateRepository(session)
        self.director = DirectorService(session)
        self.registry = AssetRegistry(session)

    async def generate_for_gate(self, project_id: str, gate_id: str) -> dict[str, Any]:
        gate = await self.gates.get(UUID(gate_id))
        if gate is None or gate.status != HumanGateStatus.APPROVED.value:
            raise GateNotApprovedError(
                f"Gate {gate_id} is {getattr(gate, 'status', 'missing')}, not approved."
            )

        script = script_from_gate_payload(gate.payload)
        narration = script.full_narration

        await self.director._set_project_status(project_id, ProjectStatus.GENERATING_AUDIO)

        summary = await self.director.build_summary(project_id)
        decision = self.director._decide(
            summary,
            PipelineState(has_research=True, has_script=True, script_gate_status="approved"),
        )

        async def executor(arguments: dict[str, Any]) -> dict[str, Any]:
            tts = get_tts_provider()
            audio = await tts.synthesize(arguments["narration"])

            if audio.words:
                # The voice reported real per-word timings (Edge TTS):
                # use them directly - more exact than a transcription pass.
                transcript = TranscriptionResult(words=audio.words, duration_seconds=audio.duration_seconds)
                transcriber = "tts-timings"
            else:
                whisper = get_whisper_provider()
                transcript = await whisper.transcribe(
                    audio.audio_bytes,
                    duration_seconds=audio.duration_seconds,
                    known_text=arguments["narration"],
                )
                transcriber = f"{whisper.name}-whisper"

            sentences = extract_sentence_timestamps(transcript.words)
            beats = extract_semantic_beats(sentences)

            stored = await self.registry.store(
                project_id=project_id,
                asset_type="audio",
                content=audio.audio_bytes,
                ext=audio.format,
                created_by="audio_pipeline",
                metadata={
                    "duration_seconds": audio.duration_seconds,
                    "sample_rate": audio.sample_rate,
                    "gate_id": gate_id,
                },
            )

            return {
                "asset_id": str(stored.asset.asset_id),
                "content_hash": stored.asset.content_hash,
                "cache_hit": stored.cache_hit,
                "format": audio.format,
                "duration_seconds": audio.duration_seconds,
                "word_count": len(transcript.words),
                "words": [w.model_dump() for w in transcript.words],
                "sentences": [s.model_dump() for s in sentences],
                "beats": [b.model_dump() for b in beats],
                "model": f"{tts.name}-tts+{transcriber}",
            }

        result = await dispatch_and_audit(
            self.session,
            project_id=project_id,
            role=AgentRole.AUDIO_AGENT,
            tool_name="generate_audio",
            tool_input={"project_id": project_id, "gate_id": gate_id, "narration": narration},
            executor=executor,
            agent_decision=decision.reason,
        )

        output = dict(result.result)

        queue_event(
            self.session,
            make_event(
                event_type=EventType.AUDIO_GENERATED,
                project_id=project_id,
                payload={
                    "asset_id": output["asset_id"],
                    "duration_seconds": output["duration_seconds"],
                    "beat_count": len(output["beats"]),
                    "cache_hit": output["cache_hit"],
                },
            ),
        )

        await commit_and_publish(self.session)
        return output
