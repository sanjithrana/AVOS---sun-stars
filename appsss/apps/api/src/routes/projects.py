from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import EventType
from packages.contracts.generation import GenerateRequest, GenerateResponse, JobResponse
from packages.contracts.human_gate import HumanGateResponse
from packages.contracts.project import ProjectCreate, ProjectResponse
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, discard_queued_events, queue_event
from src.database.async_session import get_async_db
from src.errors import APIException
from src.services.generation_service import GenerationService
from src.services.human_gate_service import HumanGateService
from src.services.job_service import JobService
from src.services.project_service import ProjectNotFoundError, ProjectService

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["projects"],
)


def _not_found(project_id: str) -> APIException:
    return APIException(
        code="not_found",
        message="Project not found.",
        project_id=project_id,
        status_code=404,
    )


async def _require_project(db: AsyncSession, project_id: str) -> None:
    try:
        await ProjectService(db).get_project(project_id)
    except ProjectNotFoundError as exc:
        raise _not_found(project_id) from exc


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: AsyncSession = Depends(get_async_db),
) -> ProjectResponse:
    try:
        project = await ProjectService(db).create_project(request)
        queue_event(
            db,
            make_event(
                event_type=EventType.PROJECT_CREATED,
                project_id=project.id,
                payload={"name": project.name, "topic": project.topic},
            ),
        )
        await commit_and_publish(db)
    except Exception as exc:
        discard_queued_events(db)
        await db.rollback()
        raise APIException(
            code="internal_error",
            message="An internal error occurred.",
            status_code=500,
        ) from exc

    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_async_db),
) -> list[ProjectResponse]:
    """Dashboard project list, newest first. (Missing before: the
    dashboard's GET /projects got 405 and could never load.)"""
    projects = await ProjectService(db).list_projects()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> ProjectResponse:
    try:
        project = await ProjectService(db).get_project(project_id)
    except ProjectNotFoundError as exc:
        raise _not_found(project_id) from exc

    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/generate", response_model=GenerateResponse)
async def generate_project(
    project_id: str,
    request: GenerateRequest,
    db: AsyncSession = Depends(get_async_db),
) -> GenerateResponse:
    """Start the production workflow: research -> script -> human
    approval -> audio. Returns the job to follow (GET /jobs/{id} or SSE
    JOB_STATUS_CHANGED). Calling it again while a job is running returns
    that same job."""
    return await GenerationService(db).generate(project_id=project_id, request=request)


@router.post("/{project_id}/plan", response_model=GenerateResponse)
async def plan_project(
    project_id: str,
    request: GenerateRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_async_db),
) -> GenerateResponse:
    """Alias of /generate kept for older clients (body optional)."""
    return await GenerationService(db).generate(
        project_id=project_id,
        request=request or GenerateRequest(generation_type="video"),
    )


@router.get("/{project_id}/jobs", response_model=list[JobResponse])
async def list_project_jobs(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> list[JobResponse]:
    await _require_project(db, project_id)
    return await JobService(db).list_for_project(project_id)


@router.get("/{project_id}/gates", response_model=list[HumanGateResponse])
async def list_project_gates(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> list[HumanGateResponse]:
    """All gates, newest first - the Studio uses the latest script gate
    to render the storyboard even after it has been approved."""
    await _require_project(db, project_id)
    gates = await HumanGateService(db).list_for_project(project_id)
    return [HumanGateResponse.model_validate(g) for g in gates]


@router.get("/{project_id}/gates/pending", response_model=HumanGateResponse | None)
async def get_pending_gate(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> HumanGateResponse | None:
    gate = await HumanGateService(db).get_pending_for_project(project_id)
    return None if gate is None else HumanGateResponse.model_validate(gate)
