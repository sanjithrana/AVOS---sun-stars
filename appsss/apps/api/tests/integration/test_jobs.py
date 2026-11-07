"""
Week 1 Day 5 + Week 2 Day 10 integration checkpoint, against the live
stack (API + worker + Temporal + Postgres + Redis):

    create project -> generate -> job RUNNING -> script gate opens
    -> (job stays RUNNING while paused) -> approve -> job COMPLETED
    with generated audio, timestamps and semantic beats
    -> audit trail complete and queryable
"""

import asyncio

import httpx
import pytest

from tests.integration._live import API_URL, requires_live_api

pytestmark = requires_live_api


async def create_project(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Job Completion Integration Test",
            "topic": "Flowers",
            "duration": 30,
            "aspect_ratio": "9:16",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def wait_for(predicate, *, timeout: float = 30.0, interval: float = 0.5):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        value = await predicate()
        if value:
            return value
        await asyncio.sleep(interval)
    raise AssertionError("condition not met in time")


@pytest.mark.asyncio
async def test_full_week2_pipeline_completes_after_approval():
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        project_id = await create_project(client)

        generate = await client.post(
            f"/api/v1/projects/{project_id}/generate", json={"generation_type": "video"}
        )
        assert generate.status_code in {200, 202}
        job_id = generate.json()["job_id"]
        assert generate.json()["workflow_id"] == f"video-generation-{job_id}"

        async def pending_gate():
            r = await client.get(f"/api/v1/projects/{project_id}/gates/pending")
            assert r.status_code == 200
            return r.json()

        gate = await wait_for(pending_gate)
        assert gate["status"] == "pending"
        assert gate["payload"]["scenes"]

        # Paused: nothing proceeds without a human.
        await asyncio.sleep(2)
        paused = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        assert paused["status"] == "running"

        approve = await client.post(
            f"/api/v1/gates/{gate['id']}/approve", json={"decided_by": "integration-test"}
        )
        assert approve.status_code == 200
        assert approve.json()["status"] == "approved"

        async def finished_job():
            job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
            if job["status"] == "failed":
                pytest.fail(f"Job failed: {job}")
            return job if job["status"] == "completed" else None

        job = await wait_for(finished_job, timeout=120.0)     # visuals + QA + the final render run before it completes
        audio = job["output"]["audio"]
        assert audio["duration_seconds"] > 0
        assert audio["word_count"] > 0
        assert len(audio["beats"]) >= 1
        assert job["started_at"] is not None and job["completed_at"] is not None

        content = await client.get(f"/api/v1/assets/{audio['asset_id']}/content")
        assert content.status_code == 200
        assert content.content[:4] == b"RIFF"

        # Week 3: one ShotSpec per beat, each continuity-checked and
        # through the Blender stage before the job completes.
        n = len(audio["beats"])
        shots = (await client.get(f"/api/v1/projects/{project_id}/shots")).json()
        assert len(shots) == n
        # The job now continues into visuals + final render, so shots are
        # at BLENDER_READY *or later* (QA_PENDING once their clip exists).
        from src.services.physics_gate import POST_BLENDER_STATUSES

        assert all(s["status"] in POST_BLENDER_STATUSES and s["spec"]["physics_proxy_asset_id"] for s in shots)
        detail = (await client.get(f"/api/v1/shots/{shots[0]['id']}")).json()
        types = sorted(a["asset_type"] for a in detail["physics_assets"])
        assert types == ["blender_canny", "blender_depth", "blender_mask", "blender_normal", "physics_proxy"]
        proxy = next(a for a in detail["physics_assets"] if a["asset_type"] == "physics_proxy")
        assert all(a["parent_asset"] == proxy["asset_id"]
                   for a in detail["physics_assets"] if a["asset_type"] != "physics_proxy")
        assert all(a["metadata"]["renderer"] == "MOCK" for a in detail["physics_assets"])

        trace = (await client.get("/api/v1/agents/trace", params={"project_id": project_id})).json()
        tools = [e["tool_name"] for e in trace]
        assert tools[:4] == ["search_memory", "research_topic", "generate_script", "generate_audio"]
        assert tools[4:4 + 2 * n] == ["create_shot_spec", "validate_shot_spec"] * n
        assert tools[4 + 2 * n:4 + 3 * n] == ["run_blender_proxy"] * n
        # then the visuals stage (one clip per shot), the QA agent on every shot (v12: mock frames pass, so no
        # repairs) and the final MP4
        assert tools[4 + 3 * n:] == ["generate_video_shot"] * n + ["run_qa_committee"] * n + ["assemble_video"]
        assert all(e["status"] == "success" for e in trace)

        project = (await client.get(f"/api/v1/projects/{project_id}")).json()
        assert project["status"] == "complete"
        assert project["budget_spent"] == pytest.approx(0.01 * len(trace))


@pytest.mark.asyncio
async def test_generate_twice_returns_the_same_running_job():
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        project_id = await create_project(client)
        first = await client.post(
            f"/api/v1/projects/{project_id}/generate", json={"generation_type": "video"}
        )
        second = await client.post(
            f"/api/v1/projects/{project_id}/generate", json={"generation_type": "video"}
        )
        assert first.json()["job_id"] == second.json()["job_id"]
