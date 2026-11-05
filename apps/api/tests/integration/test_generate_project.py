import os
from uuid import UUID

import httpx
import pytest

from tests.integration._live import API_URL, requires_live_api
from sqlalchemy import text


pytestmark = requires_live_api




async def create_project(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Generate Integration Test",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 201

    project_id = response.json()["id"]
    UUID(project_id)

    return project_id


@pytest.mark.asyncio
async def test_generate_project_creates_job():
    async with httpx.AsyncClient(
        base_url=API_URL,
        timeout=30.0,
    ) as client:
        project_id = await create_project(client)

        response = await client.post(
            f"/api/v1/projects/{project_id}/generate",
            json={
                "generation_type": "video",
            },
        )

    assert response.status_code in {200, 202}

    data = response.json()

    assert data["job_id"]
    assert data["project_id"] == project_id
    assert data["status"] == "running"

    UUID(data["job_id"])

    assert data["workflow_id"].startswith(
        f"video-generation-{data['job_id']}"
    )


@pytest.mark.asyncio
async def test_generate_project_returns_workflow_id():
    async with httpx.AsyncClient(
        base_url=API_URL,
        timeout=30.0,
    ) as client:
        project_id = await create_project(client)

        response = await client.post(
            f"/api/v1/projects/{project_id}/generate",
            json={
                "generation_type": "video",
            },
        )

    assert response.status_code in {200, 202}

    data = response.json()

    assert data["workflow_id"]
    assert data["workflow_id"] == (
        f"video-generation-{data['job_id']}"
    )
