"""Edit one shot in the Studio and regenerate it: new ShotSpec version → continuity check → physics proxy →
picture + clip → the final video re-rendered with the new shot.

The edit (a new version) is saved in the request; the slow part runs in the background with its own database
sessions, and its progress is kept in REGEN (one entry per shot) for the Studio to poll.
"""
from __future__ import annotations

import logging
import time
from uuid import NAMESPACE_URL, uuid5
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.events.outbox import commit_and_publish
from src.database.async_session import AsyncSessionLocal
from src.database.models.job import JobRecord
from src.errors import APIException
from src.services.blender_stage_service import BlenderStageService
from src.services.final_render_service import FinalRenderService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shot_planning_service import ShotPlanningService
from src.services.shotspec_service import ShotSpecService

logger = logging.getLogger(__name__)

STUDIO_EDITOR_ID = uuid5(NAMESPACE_URL, "avos:human:studio-editor")   # author of versions written in the Studio
# shot_id -> {"state": running|done|error, "step": ..., "version": n, "error": str|None, "started": t, "finished": t}
REGEN: dict[str, dict[str, Any]] = {}
STEPS = ("saved", "physics", "visuals", "final", "done")

EDITABLE_CAMERA = ("shot_type", "angle", "movement", "lens_mm")
EDITABLE_ENV = ("location", "time_of_day", "weather")
EDITABLE_LIGHTING = ("key", "mood")


def apply_edit(content: ShotContent, edit: dict[str, Any]) -> ShotContent:
    """The shot's content with the Studio's edits applied (only the fields a person can change here)."""
    data = content.model_dump(mode="json")
    if "description" in edit and edit["description"] is not None:
        data["description"] = str(edit["description"]).strip()
    if "style" in edit:
        data["style"] = (str(edit["style"]).strip() or None) if edit["style"] is not None else data.get("style")
    if "prompt" in edit:
        data["prompt"] = (str(edit["prompt"]).strip() or None) if edit["prompt"] is not None else None
    for group, keys in (("camera", EDITABLE_CAMERA), ("environment", EDITABLE_ENV), ("lighting", EDITABLE_LIGHTING)):
        for k, v in (edit.get(group) or {}).items():
            if k in keys and v is not None and str(v).strip() != "":
                data[group][k] = int(v) if k == "lens_mm" else str(v).strip()
    env_in = edit.get("environment") or {}
    if env_in.get("location") and str(env_in["location"]).strip() != (content.environment.location or ""):
        data["scene_change"] = True        # a person moved this shot somewhere else on purpose
    if edit.get("new_take"):
        data["take"] = int(data.get("take") or 0) + 1
    try:
        return ShotContent.model_validate(data)
    except ValueError as exc:
        raise APIException(code="validation_error", message=f"That edit isn't valid: {exc}", status_code=422) from exc


class ShotEditService:
    def __init__(self, session) -> None:
        self.session = session
        self.specs = ShotSpecService(session)

    async def edit(self, shot_id: str, edit: dict[str, Any]) -> dict[str, Any]:
        shot = await self.specs.shots.get(shot_id)
        if shot is None:
            raise APIException(code="not_found", message="Shot not found.", status_code=404)
        if REGEN.get(shot_id, {}).get("state") == "running":
            raise APIException(code="conflict", message="This shot is already being regenerated.", status_code=409)
        current = await self.specs.shots.current_version(shot)
        content = apply_edit(ShotContent.model_validate(current.content), edit)
        if content == ShotContent.model_validate(current.content):
            content = apply_edit(content, {"new_take": True})        # nothing changed: a new take
        _, row, _ = await self.specs.create_shot_spec(shot.project_id, content, shot_index=shot.shot_index, created_by=str(STUDIO_EDITOR_ID))
        report = await self.specs.validate_shot_spec(shot.id, version=row.version, advance_world_state=False)
        await commit_and_publish(self.session)
        if not report.passed:
            msgs = "; ".join(v.message for v in report.violations if v.severity == "error") or "continuity check failed"
            raise APIException(code="conflict", message=f"Saved as v{row.version}, but it breaks continuity: {msgs}", status_code=409)
        REGEN[shot_id] = {"state": "running", "step": "saved", "version": row.version, "error": None, "started": time.time(),
                          "project_id": shot.project_id, "shot_index": shot.shot_index}
        return {"shot_id": shot_id, "version": row.version, "project_id": shot.project_id}


async def regenerate(shot_id: str, session_factory=None) -> None:
    """Background: physics proxy → picture + clip → re-render the final video. Progress in REGEN[shot_id]."""
    Session = session_factory or AsyncSessionLocal  # noqa: N806
    st = REGEN[shot_id]
    project_id = st["project_id"]
    try:
        st["step"] = "physics"
        async with Session() as s:
            await dispatch_and_audit(
                s, project_id=project_id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
                tool_input={"shot_id": shot_id}, executor=BlenderStageService(s).tool_run_blender_proxy,
                agent_decision=f"Studio edit: physics proxy for shot {st['shot_index'] + 1} v{st['version']}.",
            )
            await commit_and_publish(s)
        st["step"] = "visuals"
        from agentic_core.model_fabric import dispatch

        with dispatch.use_priority(dispatch.URGENT):    # someone is waiting in the Studio: jump the GPU queues
            async with Session() as s:
                results = await ShotPlanningService(s).run_generation_stage(project_id, only_shot_id=shot_id)
                await commit_and_publish(s)
        if not results:
            raise RuntimeError("The shot wasn't generated (its physics proxy isn't ready).")
        st["step"] = "final"
        async with Session() as s:
            job = (await s.execute(
                select(JobRecord).where(JobRecord.project_id == project_id).order_by(JobRecord.created_at.desc()).limit(1)
            )).scalar_one_or_none()
            output = dict(job.output_payload or {}) if job else {}
            audio = output.get("audio")
            if audio and output.get("final_video"):
                summary = await FinalRenderService(s).render_through_gateway(project_id, audio)
                output["final_video"] = summary
                output.setdefault("edits", []).append({"shot_index": st["shot_index"], "version": st["version"], "at": time.time()})
                job.output_payload = output
                flag_modified(job, "output_payload")
                st["final_video"] = summary
            await commit_and_publish(s)
        st.update(step="done", state="done", finished=time.time())
    except Exception as exc:  # noqa: BLE001 - shown in the Studio
        logger.exception("Regenerating shot %s failed", shot_id)
        st.update(state="error", error=str(exc)[:500], finished=time.time())
