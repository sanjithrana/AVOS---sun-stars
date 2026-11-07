from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.models.image.factory import KNOWN_PROVIDERS as KNOWN_IMAGE_PROVIDERS
from agentic_core.models.llm.factory import KNOWN_PROVIDERS as KNOWN_LLM_PROVIDERS
from agentic_core.models.video.factory import KNOWN_PROVIDERS as KNOWN_VIDEO_PROVIDERS
from agentic_core.styles import KNOWN_STYLES
from packages.contracts.project import ProjectCreate
from src.database.models.project import Project
from src.errors import APIException
from src.repositories.project_repository import ProjectRepository


class ProjectNotFoundError(Exception):
    """Raised when a requested project does not exist."""


def _validate_provider(value: str | None, known: tuple[str, ...], field: str, tasks: tuple[str, ...] = ()) -> None:
    from agentic_core import settings_store

    custom = settings_store.custom_model(value) if value and tasks else None
    if custom and custom["task"] in tasks:
        return
    if value is not None and value not in known:
        raise APIException(
            code="validation_error",
            message=f"Unknown {field} '{value}'. Known values: {', '.join(known)}" + (", or a model added in Settings." if tasks else "."),
            status_code=422,
        )


def clean_generation_policy(policy: dict | None) -> dict | None:
    """Validate a project's Model Fabric limits (same rules as Settings → Model Fabric)."""
    if not policy:
        return None
    from agentic_core import settings_store
    from agentic_core.models import catalog

    try:
        clean = settings_store.clean_policy(policy)
    except ValueError as exc:
        raise APIException(code="validation_error", message=str(exc), status_code=422) from exc
    for k in ("preferred_model", "fallback_model"):
        if clean.get(k):
            try:
                catalog.get(clean[k])
            except KeyError as exc:
                raise APIException(code="validation_error", message=f"Unknown {k} '{clean[k]}'.", status_code=422) from exc
    return clean or None


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ProjectRepository(session)

    async def create_project(
        self,
        request: ProjectCreate,
    ) -> Project:
        # "mock" is always accepted even though it isn't in the image/
        # video factories' KNOWN_PROVIDERS (it means "no real provider",
        # not a real one - see those factories' get_*_provider).
        _validate_provider(request.llm_provider, (*KNOWN_LLM_PROVIDERS, "mock"), "llm_provider", ("llm",))
        _validate_provider(request.image_provider, (*KNOWN_IMAGE_PROVIDERS, "mock"), "image_provider", ("image",))
        _validate_provider(request.video_provider, (*KNOWN_VIDEO_PROVIDERS, "mock"), "video_provider", ("video", "avatar"))
        _validate_provider(request.style_preset, KNOWN_STYLES, "style_preset")

        return await self.repository.create(
            name=request.name,
            topic=request.topic,
            duration_seconds=request.duration,
            aspect_ratio=request.aspect_ratio,
            budget_limit=request.budget_limit,
            llm_provider=request.llm_provider,
            image_provider=request.image_provider,
            video_provider=request.video_provider,
            style_preset=request.style_preset,
            generation_policy=clean_generation_policy(request.generation_policy),
        )

    async def set_generation_policy(self, project_id: str, policy: dict | None) -> Project:
        project = await self.get_project(project_id)
        project.generation_policy = clean_generation_policy(policy)
        await self.repository.session.flush()
        return project

    async def list_projects(self, limit: int = 100) -> list[Project]:
        return await self.repository.list_all(limit=limit)

    async def get_project(
        self,
        project_id: str,
    ) -> Project:
        project = await self.repository.get(project_id)

        if project is None:
            raise ProjectNotFoundError(project_id)

        return project
