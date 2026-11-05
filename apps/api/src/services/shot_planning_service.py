"""
Director: plan the shot list from the approved script's semantic beats
(Week 3 Day 11/12).

    latest approved script + generated audio (Week 2)
      -> agentic_core ShotSpec builder (one draft per beat)
      -> for each shot, through the audited Tool Gateway:
           create_shot_spec   (Director, "planning")
           validate_shot_spec (Director, "planning") - continuity vs WorldState
      -> for each PLANNED shot, delegated to the Physics agent:
           run_blender_proxy  (Physics, "blender")  - depth/normal/canny/mask

Physics before pixels: nothing here generates pixels. Video generation
(generate_video_shot) is rejected by the Gateway with MISSING_DEPENDENCY
until run_blender_proxy has completed for the shot's current version
(see services/physics_gate.py).
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.shotspec.builder import build_shot_specs
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.audio import SemanticBeat, SentenceTimestamp
from packages.contracts.human_gate import HumanGateStatus, HumanGateType
from packages.contracts.world_state import WorldState
from src.database.models.human_gate import HumanGate
from src.database.models.job import JobRecord
from src.errors import APIException
from src.core.blender.client import BlenderClient
from src.services.audio_service import script_from_gate_payload
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationService


class ShotPlanningPrerequisiteError(RuntimeError):
    """No approved script + generated audio to plan shots from yet."""


class ShotPlanningService:
    def __init__(self, session: AsyncSession, *, blender_client: BlenderClient | None = None) -> None:
        self.session = session
        self.shotspecs = ShotSpecService(session)
        self.blender = BlenderStageService(session, client=blender_client)
        self.video = VideoGenerationService(session)

    async def _latest_audio(self, project_id: str) -> dict[str, Any]:
        result = await self.session.execute(
            select(JobRecord)
            .where(JobRecord.project_id == project_id, JobRecord.output_payload.is_not(None))
            .order_by(JobRecord.created_at.desc())
        )
        for job in result.scalars():
            audio = (job.output_payload or {}).get("audio")
            if audio and audio.get("beats"):
                return audio
        raise ShotPlanningPrerequisiteError("No generated audio with semantic beats yet.")

    async def _approved_script(self, project_id: str):
        result = await self.session.execute(
            select(HumanGate)
            .where(
                HumanGate.project_id == project_id,
                HumanGate.gate_type == HumanGateType.SCRIPT_APPROVAL.value,
                HumanGate.status == HumanGateStatus.APPROVED.value,
            )
            .order_by(HumanGate.created_at.desc())
        )
        gate = result.scalars().first()
        if gate is None:
            raise ShotPlanningPrerequisiteError("No approved script yet.")
        return script_from_gate_payload(gate.payload)

    async def plan_shots(
        self,
        project_id: str,
        *,
        audio: dict[str, Any] | None = None,
        run_blender: bool = True,
        run_generation: bool = True,
    ) -> list[dict[str, Any]]:
        """Create + continuity-validate one ShotSpec per semantic beat.

        Only *missing* shots are created: a shot that already exists keeps
        its versions untouched, so re-planning never reverts a human edit
        (versions are only added by explicit edits). Returns summaries."""
        audio = audio or await self._latest_audio(project_id)
        script = await self._approved_script(project_id)
        world = WorldState.model_validate(
            (await self.shotspecs.get_world_state(project_id)).state.model_dump()
        )

        drafts = build_shot_specs(
            project_id=project_id,
            beats=[SemanticBeat.model_validate(b) for b in audio["beats"]],
            sentences=[SentenceTimestamp.model_validate(s) for s in audio["sentences"]],
            total_duration=float(audio["duration_seconds"]),
            scenes=script.scenes,
            world_state=world,
        )

        summaries = []
        for draft in drafts:
            existing = await self.shotspecs.shots.get_by_index(project_id, draft.shot_index)
            if existing is not None:
                summaries.append({
                    "shot_id": existing.id,
                    "shot_index": existing.shot_index,
                    "version": existing.current_version,
                    "skipped": True,
                })
                continue

            created = await dispatch_and_audit(
                self.session,
                project_id=project_id,
                role=AgentRole.DIRECTOR,
                tool_name="create_shot_spec",
                tool_input={
                    "project_id": project_id,
                    "shot_index": draft.shot_index,
                    "content": draft.content.model_dump(mode="json"),
                },
                executor=self.shotspecs.tool_create_shot_spec,
                agent_decision=(
                    f"Shot {draft.shot_index + 1}/{len(drafts)} for {draft.content.beat_label} "
                    f"({draft.content.start_time:.1f}-{draft.content.end_time:.1f}s): "
                    f"{draft.content.camera.shot_type.value.replace('_', ' ')} shot."
                ),
            )
            shot_id = created.result["shot_id"]

            report = await dispatch_and_audit(
                self.session,
                project_id=project_id,
                role=AgentRole.DIRECTOR,
                tool_name="validate_shot_spec",
                tool_input={"shot_id": shot_id, "advance_world_state": True},
                executor=self.shotspecs.tool_validate_shot_spec,
                agent_decision=f"Checking shot {draft.shot_index + 1} against the WorldState for continuity.",
            )
            summaries.append({
                "shot_id": shot_id,
                "shot_index": draft.shot_index,
                "version": created.result["version"],
                "skipped": False,
                "continuity_passed": report.result["passed"],
                "violations": [v["code"] for v in report.result["violations"]],
            })

        if run_blender:
            await self.run_blender_stage(project_id, summaries)
            if run_generation:
                await self.run_generation_stage(project_id, summaries)
        return summaries

    async def run_blender_stage(
        self, project_id: str, summaries: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Physics proxy for every shot whose current version is PLANNED
        and not yet rendered (new shots, and human edits that have since
        passed validation). FAILED/DRAFT versions are left alone."""
        summaries = summaries if summaries is not None else []
        by_id = {s["shot_id"]: s for s in summaries}
        rendered_shots: list[dict[str, Any]] = []
        shots = await self.shotspecs.shots.list_by_project(project_id)
        for shot in shots:
            current = await self.shotspecs.shots.current_version(shot)
            summary = by_id.get(shot.id)
            if current is None or current.physics_proxy_asset_id is not None:
                if summary is not None and current is not None:
                    summary["physics_proxy_asset_id"] = (
                        str(current.physics_proxy_asset_id) if current.physics_proxy_asset_id else None
                    )
                continue
            if current.status != "PLANNED":
                if summary is not None:
                    summary["physics_proxy_asset_id"] = None
                continue

            rendered = await dispatch_and_audit(
                self.session,
                project_id=project_id,
                role=AgentRole.PHYSICS_AGENT,
                tool_name="run_blender_proxy",
                tool_input={"shot_id": shot.id, "version": current.version},
                executor=self.blender.tool_run_blender_proxy,
                agent_decision=(
                    f"Director -> Physics: Blender proxy (depth/normal/canny/mask) for shot "
                    f"{shot.shot_index + 1} v{current.version} before any pixels."
                ),
            )
            rendered_shots.append(rendered.result)
            if summary is not None:
                summary["physics_proxy_asset_id"] = rendered.result["physics_proxy_asset_id"]
                summary["renderer"] = rendered.result["renderer"]
        return rendered_shots

    async def run_generation_stage(
        self,
        project_id: str,
        summaries: list[dict[str, Any]] | None = None,
        *,
        only_shot_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Week 3 Day 13: generate 3 candidates for every shot whose
        Blender stage is done (BLENDER_READY) and hasn't been generated
        yet. Idempotent per-shot via VideoGenerationService's
        idempotency-key default, so re-running this (a retried Temporal
        activity, a repeated 'Plan shots' click) never double-generates."""
        summaries = summaries if summaries is not None else []
        by_id = {s["shot_id"]: s for s in summaries}
        generated: list[dict[str, Any]] = []
        shots = await self.shotspecs.shots.list_by_project(project_id)
        for shot in shots:
            if only_shot_id is not None and shot.id != only_shot_id:
                continue
            current = await self.shotspecs.shots.current_version(shot)
            summary = by_id.get(shot.id)
            if current is None or current.physics_proxy_asset_id is None:
                continue
            if current.video_generation_asset_id is not None or current.status != "BLENDER_READY":
                if summary is not None and current.video_generation_asset_id is not None:
                    summary["video_generation_asset_id"] = str(current.video_generation_asset_id)
                continue

            result = await dispatch_and_audit(
                self.session,
                project_id=project_id,
                role=AgentRole.VIDEO_AGENT,
                tool_name="generate_video_shot",
                tool_input={
                    "shot_id": shot.id,
                    "physics_proxy_asset_id": str(current.physics_proxy_asset_id),
                },
                executor=self.video.tool_generate_video_shot,
                agent_decision=(
                    f"Director -> Video agent: 3 candidates for shot {shot.shot_index + 1} "
                    f"v{current.version}, conditioned on its physics proxy."
                ),
            )
            generated.append(result.result)
            if summary is not None:
                summary["video_generation_id"] = result.result["video_generation_id"]
                summary["candidates"] = result.result["candidates"]
        return generated


def prerequisite_error(exc: ShotPlanningPrerequisiteError, project_id: str) -> APIException:
    return APIException(code="conflict", message=str(exc), project_id=project_id, status_code=409)
