from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.tool_gateway.permissions import AgentRole

from packages.contracts.qa_repair_api import QAResultResponse, RepairPlanResponse, ShotQAStateResponse
from packages.contracts.shot_api import (
    CreateShotSpecRequest,
    ShotDetailResponse,
    ShotResponse,
)
from packages.contracts.shotspec import ContinuityReport
from packages.contracts.world_state import WorldStateResponse
from src.core.events.outbox import commit_and_publish
from src.database.async_session import get_async_db
from src.errors import APIException
from src.repositories.qa_repository import QARepository
from src.repositories.repair_repository import RepairRepository
from src.services.approval_service import ApprovalService, ApprovalServiceError
from src.services.blender_stage_service import BlenderStageError, BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.qa_service import (
    QACommitteeService,
    QAServiceError,
    qa_result_response,
    repair_plan_response,
    shot_qa_state,
)
from src.services.repair_service import RepairService, RepairServiceError
from src.services.shot_planning_service import (
    ShotPlanningPrerequisiteError,
    ShotPlanningService,
    prerequisite_error,
)
from src.services.shot_edit_service import REGEN, ShotEditService, regenerate
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationError, VideoGenerationService

router = APIRouter(prefix="/api/v1", tags=["shots"])


@router.get("/projects/{project_id}/shots", response_model=list[ShotResponse])
async def list_shots(project_id: str, db: AsyncSession = Depends(get_async_db)) -> list[ShotResponse]:
    """Storyboard: every shot with its current ShotSpec version."""
    shots = await ShotSpecService(db).list_shots(project_id)
    await db.commit()  # may have created world state v0
    return shots


@router.post(
    "/projects/{project_id}/shots",
    response_model=ShotDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_shot_spec(
    project_id: str,
    request: CreateShotSpecRequest,
    db: AsyncSession = Depends(get_async_db),
) -> ShotDetailResponse:
    """New shot, or a new version when a shot already exists at shot_index."""
    service = ShotSpecService(db)
    shot, _, _ = await service.create_shot_spec(project_id, request.content, shot_index=request.shot_index)
    await commit_and_publish(db)
    return await service.get_shot(shot.id)


@router.post("/projects/{project_id}/shots/plan", response_model=list[ShotResponse])
async def plan_shots(project_id: str, db: AsyncSession = Depends(get_async_db)) -> list[ShotResponse]:
    """Director: build + validate one ShotSpec per semantic beat of the
    approved script's narration (409 until audio exists)."""
    try:
        await ShotPlanningService(db).plan_shots(project_id)
    except ShotPlanningPrerequisiteError as exc:
        raise prerequisite_error(exc, project_id) from exc
    await commit_and_publish(db)
    return await ShotSpecService(db).list_shots(project_id)


@router.get("/shots/{shot_id}", response_model=ShotDetailResponse)
async def get_shot(shot_id: str, db: AsyncSession = Depends(get_async_db)) -> ShotDetailResponse:
    return await ShotSpecService(db).get_shot(shot_id)


@router.post("/shots/{shot_id}/validate", response_model=ContinuityReport)
async def validate_shot_spec(
    shot_id: str,
    version: int | None = None,
    db: AsyncSession = Depends(get_async_db),
) -> ContinuityReport:
    """Continuity check only (does not advance the WorldState)."""
    report = await ShotSpecService(db).validate_shot_spec(shot_id, version=version, advance_world_state=False)
    await commit_and_publish(db)
    return report


@router.get("/projects/{project_id}/world-state", response_model=WorldStateResponse)
async def get_world_state(project_id: str, db: AsyncSession = Depends(get_async_db)) -> WorldStateResponse:
    world = await ShotSpecService(db).get_world_state(project_id)
    await db.commit()
    return world


@router.post("/shots/{shot_id}/blender", response_model=ShotDetailResponse)
async def run_blender_proxy(shot_id: str, db: AsyncSession = Depends(get_async_db)) -> ShotDetailResponse:
    """Blender stage for one shot, through the audited Gateway (Physics
    agent). Idempotent; 409 unless the current version is PLANNED."""
    service = ShotSpecService(db)
    shot = await service.shots.get(shot_id)
    if shot is None:
        raise APIException(code="not_found", message="Shot not found.", status_code=404)
    try:
        await dispatch_and_audit(
            db,
            project_id=shot.project_id,
            role=AgentRole.PHYSICS_AGENT,
            tool_name="run_blender_proxy",
            tool_input={"shot_id": shot.id},
            executor=BlenderStageService(db).tool_run_blender_proxy,
            agent_decision=f"Human requested the Blender proxy for shot {shot.shot_index + 1}.",
        )
    except BlenderStageError as exc:
        await commit_and_publish(db)  # keep the failed call's audit row
        raise APIException(code="conflict", message=str(exc), status_code=409) from exc
    await commit_and_publish(db)
    return await service.get_shot(shot_id)


@router.post("/shots/{shot_id}/generate", response_model=ShotDetailResponse)
async def generate_video_shot(
    shot_id: str,
    idempotency_key: str | None = None,
    db: AsyncSession = Depends(get_async_db),
) -> ShotDetailResponse:
    """
    Video agent, through the audited + physics-gated Gateway (Week 3 Day
    13). Uses the shot's current version's physics proxy automatically -
    a human clicking "Generate" doesn't need to know the proxy id.

    Idempotent: an optional ?idempotency_key= lets a client guarantee a
    repeated call (e.g. a retried request) returns the first call's
    candidates rather than generating again (AVOS-03 v1.1 s9.5); without
    one, the same default-derived key still makes an accidental double
    submit safe. 409 unless the Blender stage has completed for this
    shot's current version.
    """
    service = ShotSpecService(db)
    shot = await service.shots.get(shot_id)
    if shot is None:
        raise APIException(code="not_found", message="Shot not found.", status_code=404)
    current = await service.shots.current_version(shot)
    if current is None or current.physics_proxy_asset_id is None:
        raise APIException(
            code="conflict",
            message=f"Shot {shot.shot_index + 1} has no physics proxy yet; run the Blender stage first.",
            status_code=409,
        )
    try:
        await dispatch_and_audit(
            db,
            project_id=shot.project_id,
            role=AgentRole.VIDEO_AGENT,
            tool_name="generate_video_shot",
            tool_input={
                "shot_id": shot.id,
                "physics_proxy_asset_id": str(current.physics_proxy_asset_id),
                "idempotency_key": idempotency_key,
            },
            executor=VideoGenerationService(db).tool_generate_video_shot,
            agent_decision=f"Human requested generation for shot {shot.shot_index + 1}.",
        )
    except VideoGenerationError as exc:
        await commit_and_publish(db)
        raise APIException(code="conflict", message=str(exc), status_code=409) from exc
    await commit_and_publish(db)
    return await service.get_shot(shot_id)


@router.get("/shots/{shot_id}/qa", response_model=ShotQAStateResponse)
async def get_shot_qa_state(shot_id: str, db: AsyncSession = Depends(get_async_db)) -> ShotQAStateResponse:
    """QADashboard: latest QA verdict + every repair attempt so far, in
    one call."""
    return await shot_qa_state(QARepository(db), RepairRepository(db), shot_id)


@router.post("/shots/{shot_id}/qa", response_model=QAResultResponse)
async def run_qa_committee(
    shot_id: str,
    candidate_index: int = 0,
    force_fail: bool = False,
    db: AsyncSession = Depends(get_async_db),
) -> QAResultResponse:
    """
    QA agent, through the audited Gateway (Week 3 Day 14). Scores the
    shot's generated candidate across the 6 AVOS-06 QA dimensions and
    moves the version to PASSED or FAILED. 409 until a candidate exists
    to judge (run generate_video_shot first).

    ?force_fail=true (Week 3 Day 15) still runs the real evaluation, then
    deliberately overrides the real dimensions to FAIL - loudly
    (evidence.forced=true, a dedicated "forced_failure" issue on each
    overridden dimension) - so the repair ladder can be proven live
    through this same endpoint instead of only against a pytest fixture.
    """
    service = ShotSpecService(db)
    shot = await service.shots.get(shot_id)
    if shot is None:
        raise APIException(code="not_found", message="Shot not found.", status_code=404)
    try:
        result = await dispatch_and_audit(
            db,
            project_id=shot.project_id,
            role=AgentRole.QA_AGENT,
            tool_name="run_qa_committee",
            tool_input={"shot_id": shot.id, "candidate_index": candidate_index, "force_fail": force_fail},
            executor=QACommitteeService(db).tool_run_qa_committee,
            agent_decision=(
                f"QA committee: scoring shot {shot.shot_index + 1}'s candidate {candidate_index}."
                + (" (verdict forced to FAIL for the Day 15 integration checkpoint)" if force_fail else "")
            ),
        )
    except QAServiceError as exc:
        await commit_and_publish(db)
        raise APIException(code="conflict", message=str(exc), status_code=409) from exc
    await commit_and_publish(db)
    row = await QARepository(db).get_latest_for_shot(shot_id)
    assert row is not None and str(row.id) == result.result["qa_result_id"]
    return qa_result_response(row)


@router.post("/shots/{shot_id}/repair", response_model=RepairPlanResponse)
async def repair_shot(shot_id: str, db: AsyncSession = Depends(get_async_db)) -> RepairPlanResponse:
    """
    Repair agent, through the audited Gateway (Week 3 Day 14). Advances
    the shot's repair ladder one attempt: MICRO (1st) and MACRO (2nd)
    regenerate candidates and put the shot back in QA_PENDING;
    HUMAN_REQUIRED (3rd+) applies nothing and needs a human. The attempt
    number is derived from how many repair_plans rows this shot already
    has - durable across a worker restart by construction (AVOS-03 v1.1
    s14.6). 409 unless the shot's latest QA result is a FAIL.
    """
    service = ShotSpecService(db)
    shot = await service.shots.get(shot_id)
    if shot is None:
        raise APIException(code="not_found", message="Shot not found.", status_code=404)
    try:
        result = await dispatch_and_audit(
            db,
            project_id=shot.project_id,
            role=AgentRole.REPAIR_AGENT,
            tool_name="repair_shot",
            tool_input={"shot_id": shot.id},
            executor=RepairService(db).tool_repair_shot,
            agent_decision=f"Human requested repair for shot {shot.shot_index + 1}.",
        )
    except RepairServiceError as exc:
        await commit_and_publish(db)
        raise APIException(code="conflict", message=str(exc), status_code=409) from exc
    await commit_and_publish(db)
    rows = await RepairRepository(db).list_for_shot(shot_id)
    latest = next(r for r in rows if str(r.id) == result.result["repair_plan_id"])
    return repair_plan_response(latest)


@router.post("/shots/{shot_id}/approve", response_model=ShotDetailResponse)
async def approve_shot(shot_id: str, db: AsyncSession = Depends(get_async_db)) -> ShotDetailResponse:
    """
    The stubbed final gate (Week 3 Day 15, AVOS-18 s6.3): a human signs
    off on a QA-PASSED shot. Dispatched as the Director (the "approval"
    tool scope) through the same audited Gateway as every other decision
    here. 409 unless the shot's current version's latest QA result is a
    PASS. Final Assembly/FFmpeg isn't built yet (Week 4+ ticket) - this
    is the entire final stage for now.
    """
    service = ShotSpecService(db)
    shot = await service.shots.get(shot_id)
    if shot is None:
        raise APIException(code="not_found", message="Shot not found.", status_code=404)
    try:
        await dispatch_and_audit(
            db,
            project_id=shot.project_id,
            role=AgentRole.DIRECTOR,
            tool_name="approve_shot",
            tool_input={"shot_id": shot.id},
            executor=ApprovalService(db).tool_approve_shot,
            agent_decision=f"Human approved shot {shot.shot_index + 1} at the final gate.",
        )
    except ApprovalServiceError as exc:
        await commit_and_publish(db)
        raise APIException(code="conflict", message=str(exc), status_code=409) from exc
    await commit_and_publish(db)
    return await service.get_shot(shot_id)


# ---------- Studio: edit a shot and regenerate it ----------


@router.post("/shots/{shot_id}/edit")
async def edit_shot(shot_id: str, request: Request, background: BackgroundTasks,
                    db: AsyncSession = Depends(get_async_db)) -> dict[str, Any]:
    """Save the Studio's edits (description, camera, environment, lighting, style, or the exact prompt) as a new
    version and regenerate the shot in the background (physics proxy, picture + clip, final video). Sending no
    changes makes a new take with fresh seeds."""
    body = await request.json() if (await request.body()) else {}
    if not isinstance(body, dict):
        raise APIException(code="validation_error", message="Send a JSON object.", status_code=422)
    result = await ShotEditService(db).edit(shot_id, body)
    background.add_task(regenerate, shot_id)
    return {**result, "regen": REGEN[shot_id]}


@router.get("/shots/{shot_id}/regenerate")
async def regenerate_status(shot_id: str) -> dict[str, Any]:
    return REGEN.get(shot_id) or {"state": "idle"}
