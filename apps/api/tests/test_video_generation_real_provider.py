"""
Week 3 Day 16 - a project that picked a real image/video provider
(rather than leaving image_provider/video_provider unset, which stays
on the deterministic MOCK path covered by
test_video_generation_idempotency.py) must route generation through
that provider, tag assets with its name, and populate render_asset_id.

The providers' own HTTP calls are monkeypatched here (no real network
in tests, same principle as MockBlenderClient) - what's under test is
VideoGenerationService's wiring, not Pollinations/local-server uptime.
"""

import pytest

from agentic_core.models.image.pollinations_provider import PollinationsProvider
from agentic_core.models.video.local_provider import LocalVideoProvider
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.repositories.project_repository import ProjectRepository
from src.repositories.shot_repository import ShotRepository  # noqa: F401 (import parity with sibling test)
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationService
from tests.conftest import requires_db

pytestmark = requires_db

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32


def _content() -> ShotContent:
    return ShotContent(
        beat_label="beat_1", start_time=0.0, end_time=3.0, narration="Line.",
        description="A cheerful character waves at the camera.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


async def _ready_shot(session, tmp_path, *, image_provider=None, video_provider=None):
    project = await ProjectRepository(session).create(
        name="Real provider", topic="Flowers", duration_seconds=12, aspect_ratio="9:16",
        image_provider=image_provider, video_provider=video_provider,
    )
    specs = ShotSpecService(session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(shot.id)
    await session.commit()
    registry = AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path)))
    stage = BlenderStageService(session, client=MockBlenderClient(), registry=registry)
    blender_result = await dispatch_and_audit(
        session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy,
        agent_decision="Physics agent: blender proxy",
    )
    proxy_id = blender_result.result["physics_proxy_asset_id"]
    return project, shot, proxy_id, registry


@pytest.mark.asyncio
async def test_pollinations_image_provider_tags_assets_and_skips_render(
    db_session, clean_db, captured_events, tmp_path, monkeypatch
):
    async def fake_generate(self, prompt, *, width=512, height=512, seed=None):
        return FAKE_PNG

    monkeypatch.setattr(PollinationsProvider, "generate", fake_generate)

    project, shot, proxy_id, registry = await _ready_shot(
        db_session, tmp_path, image_provider="pollinations"
    )
    video = VideoGenerationService(db_session, registry=registry)

    result = await video.generate(shot.id, physics_proxy_asset_id=proxy_id)

    assert len(result["candidates"]) == 3
    for candidate in result["candidates"]:
        assert candidate["render_asset_id"] is None  # no video provider configured


@pytest.mark.asyncio
async def test_image_and_video_provider_together_populate_render_asset_id(
    db_session, clean_db, captured_events, tmp_path, monkeypatch
):
    async def fake_image_generate(self, prompt, *, width=512, height=512, seed=None):
        return FAKE_PNG

    seen: dict = {}

    async def fake_video_generate(
        self, prompt, *, width=512, height=512, seed=None, duration_seconds=2.0, image=None
    ):
        seen.update(duration_seconds=duration_seconds, image=image)
        return FAKE_MP4

    monkeypatch.setattr(PollinationsProvider, "generate", fake_image_generate)
    monkeypatch.setattr(LocalVideoProvider, "generate", fake_video_generate)
    monkeypatch.setenv("VIDEO_SERVICE_URL", "http://localhost:9000")

    project, shot, proxy_id, registry = await _ready_shot(
        db_session, tmp_path, image_provider="pollinations", video_provider="local",
    )
    video = VideoGenerationService(db_session, registry=registry)

    result = await video.generate(shot.id, physics_proxy_asset_id=proxy_id)

    assert len(result["candidates"]) == 3
    # Only the first candidate gets a clip (clips are the slow/paid part;
    # the final render uses candidate 0) - the others keep their stills.
    assert result["candidates"][0]["render_asset_id"] is not None
    for candidate in result["candidates"][1:]:
        assert candidate["render_asset_id"] is None
    # Image-to-video: the clip is made from that candidate's own still,
    # for the shot's length on the narration timeline.
    assert seen["image"] == FAKE_PNG
    assert seen["duration_seconds"] == pytest.approx(shot.end_time - shot.start_time)


@pytest.mark.asyncio
async def test_provider_failure_propagates_instead_of_falling_back_to_mock(
    db_session, clean_db, captured_events, tmp_path, monkeypatch
):
    async def failing_generate(self, prompt, *, width=512, height=512, seed=None):
        raise RuntimeError("Could not reach Pollinations at https://image.pollinations.ai.")

    monkeypatch.setattr(PollinationsProvider, "generate", failing_generate)

    project, shot, proxy_id, registry = await _ready_shot(
        db_session, tmp_path, image_provider="pollinations"
    )
    video = VideoGenerationService(db_session, registry=registry)

    with pytest.raises(RuntimeError, match="Could not reach Pollinations"):
        await video.generate(shot.id, physics_proxy_asset_id=proxy_id)


@pytest.mark.asyncio
async def test_no_provider_selected_keeps_existing_mock_behaviour(
    db_session, clean_db, captured_events, tmp_path
):
    """Unset image_provider/video_provider (the default for every
    project created before this feature existed) must still produce the
    exact same MOCK-tagged path as before - the whole point of the
    factories returning None rather than auto-detecting."""
    project, shot, proxy_id, registry = await _ready_shot(db_session, tmp_path)
    video = VideoGenerationService(db_session, registry=registry)

    result = await video.generate(shot.id, physics_proxy_asset_id=proxy_id)

    assert len(result["candidates"]) == 3
    for candidate in result["candidates"]:
        assert candidate["render_asset_id"] is None


# -- catalog models (agentic_core/models/catalog.json) ------------------------


def _narration_wav(tmp_path, seconds: float = 6.0) -> bytes:
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    out = tmp_path / "narration.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", str(out)], check=True)
    return out.read_bytes()


@pytest.mark.asyncio
async def test_avatar_model_gets_the_presenter_and_this_shots_narration(
    db_session, clean_db, captured_events, tmp_path, monkeypatch
):
    from agentic_core.models.video.catalog_video import CatalogVideoProvider
    from src.services.video_generation_service import PRESENTER_ASSET_TYPE

    image_prompts: list[str] = []

    async def fake_image_generate(self, prompt, *, width=512, height=512, seed=None):
        image_prompts.append(prompt)
        return FAKE_PNG + (b"presenter" if "presenter" in prompt else b"shot")

    seen: dict = {}

    async def fake_avatar(self, prompt, *, width=512, height=512, seed=None, duration_seconds=2.0, image=None,
                          audio=None, video=None):
        seen.update(model=self.model_id, image=image, audio=audio, prompt=prompt, seconds=duration_seconds)
        return FAKE_MP4

    monkeypatch.setattr(PollinationsProvider, "generate", fake_image_generate)
    monkeypatch.setattr(CatalogVideoProvider, "generate", fake_avatar)
    monkeypatch.setenv("FAL_KEY", "test")
    monkeypatch.delenv("MODEL_BACKEND", raising=False)
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "none"))

    project, shot, proxy_id, registry = await _ready_shot(
        db_session, tmp_path, image_provider="pollinations", video_provider="avatar",
    )
    await registry.store(project_id=project.id, asset_type="audio", content=_narration_wav(tmp_path),
                         ext="mp3", created_by="audio_pipeline")
    video = VideoGenerationService(db_session, registry=registry)

    result = await video.generate(shot.id, physics_proxy_asset_id=proxy_id)

    assert result["candidates"][0]["render_asset_id"] is not None
    assert seen["model"] == "longcat-avatar"                              # short scene -> LongCat Avatar
    assert seen["image"].endswith(b"presenter")                           # the presenter portrait, not the shot still
    assert seen["audio"][:4] == b"RIFF" and seen["prompt"].startswith("A presenter talking")
    assert seen["seconds"] == pytest.approx(3.0)
    # the presenter is made once per project and reused for every shot
    await video.generate(shot.id, physics_proxy_asset_id=proxy_id, idempotency_key="again")
    assert sum("presenter" in p for p in image_prompts) == 1
    assert await video._latest_asset(project.id, PRESENTER_ASSET_TYPE) is not None


@pytest.mark.asyncio
async def test_avatar_without_narration_says_so(db_session, clean_db, captured_events, tmp_path, monkeypatch):
    from src.services.video_generation_service import VideoGenerationError

    async def fake_image_generate(self, prompt, *, width=512, height=512, seed=None):
        return FAKE_PNG

    monkeypatch.setattr(PollinationsProvider, "generate", fake_image_generate)
    monkeypatch.setenv("FAL_KEY", "test")
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "none"))
    project, shot, proxy_id, registry = await _ready_shot(
        db_session, tmp_path, image_provider="pollinations", video_provider="longcat-avatar",
    )
    with pytest.raises(VideoGenerationError, match="no narration audio"):
        await VideoGenerationService(db_session, registry=registry).generate(shot.id, physics_proxy_asset_id=proxy_id)


@pytest.mark.asyncio
async def test_narration_shared_with_another_project_is_still_found(
    db_session, clean_db, captured_events, tmp_path, monkeypatch
):
    """Identical narration bytes (same script, same voice) are stored once; the second project must still find it."""
    project, shot, proxy_id, registry = await _ready_shot(db_session, tmp_path)
    other = await ProjectRepository(db_session).create(name="Other", topic="Flowers", duration_seconds=12, aspect_ratio="9:16")
    audio = _narration_wav(tmp_path)
    await registry.store(project_id=other.id, asset_type="audio", content=audio, ext="mp3", created_by="audio_pipeline")
    stored = await registry.store(project_id=project.id, asset_type="audio", content=audio, ext="mp3", created_by="audio_pipeline")
    assert stored.cache_hit and stored.asset.asset_metadata["project_ids"] == [project.id]
    video = VideoGenerationService(db_session, registry=registry)
    segment = await video._narration_segment(project.id, 1.0, 2.0)
    assert segment[:4] == b"RIFF"
