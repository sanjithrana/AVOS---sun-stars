"""
End to end through the real database and ffmpeg: a project using the
free "motion" video provider gets an AI image (Pollinations, faked here)
and a real camera-move clip per shot, then FinalRenderService stitches
the clips + narration + captions into a playable MP4 asset, audited as
`assemble_video` and announced with VIDEO_ASSEMBLED.
"""

import shutil
import subprocess
from uuid import UUID

import pytest
from sqlalchemy import select

from agentic_core.models.image.pollinations_provider import PollinationsProvider
from agentic_core.models.video.motion_provider import MotionVideoProvider
from agentic_core.pipelines.audio.tts import MockTTSProvider
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.core.blender.png import encode_png
from src.core.events.outbox import commit_and_publish
from src.database.models.audit import AuditRecord
from src.repositories.project_repository import ProjectRepository
from src.services.blender_stage_service import BlenderStageService
from src.services.final_render_service import FinalRenderService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationService
from tests.conftest import requires_db

pytestmark = [
    requires_db,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
]


def _image(width: int = 144, height: int = 256) -> bytes:
    rows = [b"".join(bytes((x * 255 // width, y * 255 // height, 160)) for x in range(width)) for y in range(height)]
    return encode_png(width, height, rows, channels=3)


def _content(index: int, start: float, end: float, narration: str) -> ShotContent:
    return ShotContent(
        beat_label=f"beat_{index + 1}", start_time=start, end_time=end, narration=narration,
        description="The Sun glowing over a calm horizon.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


async def _project_with_generated_shots(session, tmp_path, monkeypatch):
    async def fake_image(self, prompt, *, width=512, height=512, seed=None):
        return _image()

    monkeypatch.setattr(PollinationsProvider, "generate", fake_image)

    # video_provider "motion" with NO image provider: the free path must
    # fall back to Pollinations rather than animating a mock placeholder.
    project = await ProjectRepository(session).create(
        name="Sun facts", topic="The Sun", duration_seconds=30, aspect_ratio="9:16",
        video_provider="motion",
    )
    registry = AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path / "assets")))
    specs = ShotSpecService(session)
    stage = BlenderStageService(session, client=MockBlenderClient(), registry=registry)
    video = VideoGenerationService(session, registry=registry)

    lines = [(0.0, 1.5, "Meet the Sun."), (1.5, 3.0, "It is a star.")]
    for index, (start, end, line) in enumerate(lines):
        shot, _, _ = await specs.create_shot_spec(project.id, _content(index, start, end, line), shot_index=index)
        await specs.validate_shot_spec(shot.id)
        await session.commit()
        blender = await dispatch_and_audit(
            session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
            tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="physics",
        )
        result = await video.generate(shot.id, physics_proxy_asset_id=blender.result["physics_proxy_asset_id"])
        assert result["candidates"][0]["render_asset_id"], "motion provider should make a clip"
        assert result.get("clip_cost_usd", 0.0) == 0.0  # motion is free
    await session.commit()

    tts = await MockTTSProvider().synthesize("Meet the Sun. It is a star.")
    audio_asset = await registry.store(
        project_id=project.id, asset_type="audio", content=tts.audio_bytes, ext="wav", created_by="test",
    )
    words = [
        {"word": w, "start": i * 0.5, "end": i * 0.5 + 0.45}
        for i, w in enumerate("Meet the Sun. It is a star.".split())
    ]
    audio = {"asset_id": str(audio_asset.asset.asset_id), "format": "wav", "words": words,
             "duration_seconds": tts.duration_seconds}
    await session.commit()
    return project, registry, audio


@pytest.mark.asyncio
async def test_final_render_produces_playable_mp4(db_session, clean_db, captured_events, tmp_path, monkeypatch):
    project, registry, audio = await _project_with_generated_shots(db_session, tmp_path, monkeypatch)

    summary = await FinalRenderService(db_session, registry=registry).render_through_gateway(project.id, audio)
    await commit_and_publish(db_session)

    assert summary["shot_sources"] == ["clip", "clip"]
    assert summary["video_provider"] == "motion"
    assert (summary["width"], summary["height"]) == (1080, 1920)
    assert summary["duration_seconds"] >= audio["duration_seconds"]

    asset = await registry.get(UUID(summary["asset_id"]))
    assert asset.asset_type == "final_video" and asset.storage_path.endswith(".mp4")
    streams = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", asset.storage_path],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert sorted(streams) == ["audio", "video"]

    audits = (await db_session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project.id, AuditRecord.tool_name == "assemble_video")
    )).scalars().all()
    assert len(audits) == 1 and audits[0].error is None
    assert "VIDEO_ASSEMBLED" in captured_events.types()


@pytest.mark.asyncio
async def test_paid_clip_cost_is_added_to_project_budget(db_session, clean_db, captured_events, tmp_path, monkeypatch):
    """A provider's per-clip cost lands on the budget/audit trail on top of
    the flat per-call placeholder - so a paid provider's spend is visible."""
    async def fake_image(self, prompt, *, width=512, height=512, seed=None):
        return _image()

    monkeypatch.setattr(PollinationsProvider, "generate", fake_image)
    monkeypatch.setattr(MotionVideoProvider, "cost_per_clip_usd", 0.25)

    project = await ProjectRepository(db_session).create(
        name="Cost", topic="The Sun", duration_seconds=10, aspect_ratio="9:16", video_provider="motion",
    )
    registry = AssetRegistry(db_session, storage=LocalAssetStorage(str(tmp_path / "assets")))
    specs = ShotSpecService(db_session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(0, 0.0, 1.0, "Hi."), shot_index=0)
    await specs.validate_shot_spec(shot.id)
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    blender = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="physics",
    )
    before = float((await ProjectRepository(db_session).get(project.id)).budget_spent)

    await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot.id, "physics_proxy_asset_id": blender.result["physics_proxy_asset_id"]},
        executor=VideoGenerationService(db_session, registry=registry).tool_generate_video_shot,
        agent_decision="video",
    )
    after = float((await ProjectRepository(db_session).get(project.id)).budget_spent)
    assert after - before == pytest.approx(0.26)  # 0.01 placeholder + 0.25 for the clip


@pytest.mark.asyncio
async def test_style_preset_sets_world_look_and_is_validated(db_session, clean_db):
    from packages.contracts.project import ProjectCreate
    from src.errors import APIException
    from src.services.project_service import ProjectService

    service = ProjectService(db_session)
    project = await service.create_project(ProjectCreate(
        name="Gorilla", topic="1 gorilla vs 100 men", duration=30, aspect_ratio="9:16", style_preset="viral_3d",
    ))
    world = await ShotSpecService(db_session).get_world_state(project.id)
    assert "3D" in world.state.style

    with pytest.raises(APIException):
        await service.create_project(ProjectCreate(
            name="x", topic="x", duration=30, aspect_ratio="9:16", style_preset="anime-ish",
        ))
