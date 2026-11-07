"""Studio: edit a shot (description, camera, environment or the exact prompt) and regenerate just that shot."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from agentic_core.models.image.pollinations_provider import PollinationsProvider
from packages.contracts.shotspec import ShotContent
from src.database.models.video_generation import VideoGeneration
from src.errors import APIException
from src.repositories.project_repository import ProjectRepository
from src.services.shot_edit_service import REGEN, ShotEditService, apply_edit, regenerate
from src.services.shot_planning_service import ShotPlanningService
from src.services.shotspec_service import ShotSpecService
from tests.conftest import requires_db

pytestmark = requires_db

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _content(**kw) -> ShotContent:
    base = dict(beat_label="beat_1", start_time=0.0, end_time=3.0, narration="The moon has phases.",
                description="The moon over a quiet sea.", style="bright, friendly storybook illustration",
                environment={"location": "main setting", "time_of_day": "night", "weather": "clear"})
    return ShotContent(**{**base, **kw})


def test_apply_edit_changes_only_editable_fields():
    c = _content()
    e = apply_edit(c, {"description": "A crescent moon", "camera": {"shot_type": "close_up", "lens_mm": "85", "bogus": 1},
                       "environment": {"weather": "misty"}, "prompt": "  exact prompt  ", "narration": "ignored"})
    assert e.description == "A crescent moon" and e.camera.shot_type.value == "close_up" and e.camera.lens_mm == 85
    assert e.environment.weather == "misty" and e.prompt == "exact prompt" and e.narration == c.narration
    assert apply_edit(c, {"environment": {"location": "a desert"}}).scene_change
    assert apply_edit(c, {"new_take": True}).take == 1
    assert apply_edit(e, {"prompt": ""}).prompt is None


@pytest.mark.asyncio
async def test_edit_and_regenerate_one_shot(db_session, clean_db, captured_events, test_engine, monkeypatch):
    prompts = []

    async def fake_generate(self, prompt, *, width=512, height=512, seed=None):
        prompts.append(prompt)
        return FAKE_PNG

    monkeypatch.setattr(PollinationsProvider, "generate", fake_generate)
    project = await ProjectRepository(db_session).create(name="Moon", topic="Moon", duration_seconds=12, aspect_ratio="9:16",
                                                         image_provider="pollinations")
    specs = ShotSpecService(db_session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(shot.id)
    await db_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    # v2: a person writes the exact prompt; only this shot is regenerated
    out = await ShotEditService(db_session).edit(shot.id, {"prompt": "A glowing crescent moon over misty water, watercolor"})
    assert out["version"] == 2 and REGEN[shot.id]["state"] == "running"
    with pytest.raises(APIException) as busy:
        await ShotEditService(db_session).edit(shot.id, {})
    assert busy.value.status_code == 409
    await regenerate(shot.id, factory)
    assert REGEN[shot.id]["state"] == "done", REGEN[shot.id]
    assert prompts and all(p == "A glowing crescent moon over misty water, watercolor" for p in prompts)

    # nothing changed -> a new take (v3) with new seeds
    async with factory() as s:
        out = await ShotEditService(s).edit(shot.id, {"prompt": "A glowing crescent moon over misty water, watercolor"})
    assert out["version"] == 3
    await regenerate(shot.id, factory)
    async with factory() as s:
        rows = (await s.execute(select(VideoGeneration).where(VideoGeneration.shot_id == shot.id)
                                .order_by(VideoGeneration.version))).scalars().all()
        detail = await ShotSpecService(s).get_shot(shot.id)
    assert [r.version for r in rows] == [2, 3]
    assert rows[0].candidates[0]["seed"] != rows[1].candidates[0]["seed"]
    assert detail.spec.content.take == 1 and detail.current_version == 3


@pytest.mark.asyncio
async def test_continuity_breaking_edit_is_reported(db_session, clean_db, captured_events):
    project = await ProjectRepository(db_session).create(name="M", topic="M", duration_seconds=12, aspect_ratio="9:16")
    specs = ShotSpecService(db_session)
    first, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(first.id)
    second, _, _ = await specs.create_shot_spec(project.id, _content(beat_label="beat_2", start_time=3.0, end_time=6.0), shot_index=1)
    await specs.validate_shot_spec(second.id)
    await db_session.commit()
    # moving the shot somewhere else on purpose is allowed (it becomes a new scene)
    out = await ShotEditService(db_session).edit(second.id, {"environment": {"location": "a desert"}})
    assert out["version"] == 2
    REGEN.pop(second.id, None)        # (the background regeneration isn't run in this test)
    with pytest.raises(APIException) as err:
        await ShotEditService(db_session).edit(second.id, {"style": "gritty noir photo"})
    assert err.value.status_code == 409 and "continuity" in err.value.message
