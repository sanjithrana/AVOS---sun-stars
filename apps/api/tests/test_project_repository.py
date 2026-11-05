import pytest

from src.repositories.project_repository import ProjectRepository


@pytest.mark.asyncio
async def test_create_and_get_project(db_session):
    repository = ProjectRepository(db_session)

    created_project = await repository.create(
        name="Repository Test Project",
        topic="Flowers",
        duration_seconds=45,
        aspect_ratio="9:16",
    )

    await db_session.commit()

    assert created_project.id
    assert created_project.name == "Repository Test Project"
    assert created_project.topic == "Flowers"
    assert created_project.duration_seconds == 45
    assert created_project.aspect_ratio == "9:16"
    assert created_project.status == "planning"
    assert created_project.budget_spent == 0

    fetched_project = await repository.get(created_project.id)

    assert fetched_project is not None
    assert fetched_project.id == created_project.id
    assert fetched_project.name == "Repository Test Project"


@pytest.mark.asyncio
async def test_get_missing_project_returns_none(db_session):
    repository = ProjectRepository(db_session)

    project = await repository.get(
        "00000000-0000-0000-0000-000000000000"
    )

    assert project is None
