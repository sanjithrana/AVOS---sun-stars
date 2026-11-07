from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import utcnow
from src.database.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        name: str,
        topic: str,
        duration_seconds: int,
        aspect_ratio: str,
        status: str = "planning",
        budget_limit: float | None = None,
        llm_provider: str | None = None,
        image_provider: str | None = None,
        video_provider: str | None = None,
        style_preset: str | None = None,
        generation_policy: dict | None = None,
    ) -> Project:
        project = Project(
            id=str(uuid4()),
            name=name,
            topic=topic,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            status=status,
            budget_limit=budget_limit,
            budget_spent=0,
            llm_provider=llm_provider,
            image_provider=image_provider,
            video_provider=video_provider,
            style_preset=style_preset,
            generation_policy=generation_policy,
        )

        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)

        return project

    async def get(self, project_id: str) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.id == str(project_id))
        )

        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100) -> list[Project]:
        """Newest first - powers the Dashboard's GET /projects."""
        result = await self.session.execute(
            select(Project).order_by(Project.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def set_status(self, project_id: str, status: str) -> Project | None:
        project = await self.get(project_id)

        if project is None:
            return None

        project.status = status
        await self.session.flush()

        return project

    async def add_budget_spent(
        self,
        project_id: str,
        amount: float,
    ) -> Project | None:
        # Atomic in-database increment: two concurrent tool calls for the
        # same project can't lose each other's cost (read-modify-write
        # in Python could).
        result = await self.session.execute(
            update(Project)
            .where(Project.id == str(project_id))
            .values(
                budget_spent=Project.budget_spent + amount,
                updated_at=utcnow(),
            )
            .returning(Project.id)
        )

        if result.scalar_one_or_none() is None:
            return None

        project = await self.get(project_id)
        if project is not None:
            await self.session.refresh(project)
        return project
