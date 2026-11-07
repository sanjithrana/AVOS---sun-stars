"""
Week 3 Day 12 (Engineer 1): Blender stage.

- MOCK is deterministic, clearly labelled, and returns valid PNG passes
- outputs are registered in the Asset Registry with the correct
  asset_type, content_hash (= sha256 of the bytes) and parent_asset lineage
- idempotent per ShotSpec version; refuses shots that aren't PLANNED
"""

import hashlib
import json
import logging

import pytest
from sqlalchemy import select

from packages.contracts.shotspec import ShotContent
from packages.contracts.world_state import CharacterState
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import PASS_NAMES, BlenderRequest, MockBlenderClient
from src.core.blender.png import png_size
from src.database.models.asset import Asset
from src.repositories.project_repository import ProjectRepository
from src.services.blender_stage_service import (
    PROXY_ASSET_TYPE,
    BlenderStageError,
    BlenderStageService,
)
from src.services.shotspec_service import ShotSpecService
from tests.conftest import requires_db

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _request(**kw) -> BlenderRequest:
    base = dict(
        project_id="p", shot_id="s", shotspec_id="spec-1", version=1, content_hash="abc",
        aspect_ratio="9:16", content={"camera": {"shot_type": "wide"}},
    )
    base.update(kw)
    return BlenderRequest(**base)


# -- MockBlenderClient (no DB) ---------------------------------------------------


@pytest.mark.asyncio
async def test_mock_is_deterministic_valid_and_labelled(caplog):
    client = MockBlenderClient()
    with caplog.at_level(logging.WARNING):
        first = await client.render_proxy(_request())
    second = await client.render_proxy(_request())

    assert first.renderer == "MOCK" and first.is_mock
    assert any("[MOCK] Blender stage" in r.message for r in caplog.records)
    assert set(first.passes) == set(PASS_NAMES)
    assert first.passes == second.passes  # deterministic
    for name, data in first.passes.items():
        assert data.startswith(PNG_SIGNATURE), name
        assert png_size(data) == (144, 256)  # 9:16 proxy resolution
        assert b"avos:renderer\x00MOCK" in data


@pytest.mark.asyncio
async def test_mock_differs_per_shotspec_and_aspect():
    client = MockBlenderClient()
    a = await client.render_proxy(_request())
    b = await client.render_proxy(_request(shotspec_id="spec-2", content_hash="def"))
    wide = await client.render_proxy(_request(aspect_ratio="16:9"))
    assert all(a.passes[n] != b.passes[n] for n in PASS_NAMES)
    assert png_size(wide.passes["depth"]) == (256, 144)


# -- BlenderStageService (Postgres) ------------------------------------------------


async def _planned_shot(session, *, clothing="yellow shirt", index=0, project=None):
    if project is None:
        project = await ProjectRepository(session).create(
            name="Blender", topic="Flowers", duration_seconds=12, aspect_ratio="9:16"
        )
    service = ShotSpecService(session)
    content = ShotContent(
        beat_label=f"beat_{index + 1}", start_time=index * 3.0, end_time=index * 3.0 + 3.0,
        narration="Hello.", style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
        characters={"Milo": CharacterState(clothing=clothing)},
    )
    shot, _, _ = await service.create_shot_spec(project.id, content, shot_index=index)
    await service.validate_shot_spec(shot.id)
    return project, shot


def _stage(session, tmp_path) -> BlenderStageService:
    return BlenderStageService(
        session, client=MockBlenderClient(),
        registry=AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path))),
    )


@requires_db
@pytest.mark.asyncio
async def test_registers_proxy_and_passes_with_lineage(db_session, clean_db, captured_events, tmp_path):
    from src.core.events.outbox import commit_and_publish

    project, shot = await _planned_shot(db_session)
    stage = _stage(db_session, tmp_path)

    summary = await stage.run_proxy(shot.id)
    await commit_and_publish(db_session)

    assert summary["rendered"] is True and summary["renderer"] == "MOCK"
    assert summary["status"] == "BLENDER_READY" and shot.status == "BLENDER_READY"
    assert "BLENDER_RENDERED" in captured_events.types()

    assets = (await db_session.execute(select(Asset))).scalars().all()
    by_type = {a.asset_type: a for a in assets}
    assert set(by_type) == {PROXY_ASSET_TYPE, "blender_depth", "blender_normal", "blender_canny", "blender_mask"}

    proxy = by_type[PROXY_ASSET_TYPE]
    assert str(proxy.asset_id) == summary["physics_proxy_asset_id"]
    assert proxy.parent_asset is None
    doc = json.loads(stage.registry.read_bytes(proxy))
    assert doc["renderer"] == "MOCK" and doc["shot_id"] == shot.id

    for name in PASS_NAMES:
        asset = by_type[f"blender_{name}"]
        data = stage.registry.read_bytes(asset)
        assert asset.parent_asset == proxy.asset_id  # lineage
        assert asset.content_hash == hashlib.sha256(data).hexdigest()
        assert doc["passes"][name] == asset.content_hash
        meta = asset.asset_metadata
        assert meta["renderer"] == "MOCK" and meta["mock"] is True and meta["pass"] == name
        assert (meta["shot_id"], meta["shotspec_version"], meta["project_id"]) == (shot.id, 1, project.id)
        assert (meta["width"], meta["height"]) == (144, 256)
        assert asset.source == "blender_mock"

    detail = await ShotSpecService(db_session).get_shot(shot.id)
    assert str(detail.spec.physics_proxy_asset_id) == summary["physics_proxy_asset_id"]
    assert len(detail.physics_assets) == 5


@requires_db
@pytest.mark.asyncio
async def test_idempotent_and_refuses_unplanned(db_session, clean_db, captured_events, tmp_path):
    project, shot = await _planned_shot(db_session)
    stage = _stage(db_session, tmp_path)

    first = await stage.run_proxy(shot.id)
    again = await stage.run_proxy(shot.id)
    assert again["rendered"] is False
    assert again["physics_proxy_asset_id"] == first["physics_proxy_asset_id"]
    assert len((await db_session.execute(select(Asset))).scalars().all()) == 5

    # A continuity-failing shot never reaches the Blender stage.
    _, bad = await _planned_shot(db_session, clothing="red jacket", index=1, project=project)
    assert bad.status == "FAILED"
    with pytest.raises(BlenderStageError):
        await stage.run_proxy(bad.id)


@requires_db
@pytest.mark.asyncio
async def test_distinct_shots_get_distinct_assets(db_session, clean_db, captured_events, tmp_path):
    project, s0 = await _planned_shot(db_session)
    _, s1 = await _planned_shot(db_session, index=1, project=project)
    stage = _stage(db_session, tmp_path)
    a = await stage.run_proxy(s0.id)
    b = await stage.run_proxy(s1.id)
    assert a["physics_proxy_asset_id"] != b["physics_proxy_asset_id"]
    assert set(a["passes"].values()).isdisjoint(b["passes"].values())
    assert len((await db_session.execute(select(Asset))).scalars().all()) == 10
