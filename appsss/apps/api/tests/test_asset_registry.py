"""Day 9: store + retrieve by content hash; duplicate content is a cache hit."""

import pytest

from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.repositories.project_repository import ProjectRepository
from tests.conftest import requires_db

pytestmark = requires_db


@pytest.mark.asyncio
async def test_store_retrieve_and_cache_hit(db_session, clean_db, tmp_path):
    project = await ProjectRepository(db_session).create(
        name="p", topic="t", duration_seconds=10, aspect_ratio="9:16"
    )
    registry = AssetRegistry(db_session, storage=LocalAssetStorage(str(tmp_path)))
    audio = b"RIFF" + b"\x00" * 100

    first = await registry.store(
        project_id=project.id, asset_type="audio", content=audio, ext="wav", created_by="test"
    )
    await db_session.commit()

    assert first.cache_hit is False
    assert registry.read_bytes(first.asset) == audio
    assert (await registry.get_by_hash(first.asset.content_hash)).asset_id == first.asset.asset_id

    second = await registry.store(
        project_id=project.id, asset_type="audio", content=audio, ext="wav", created_by="test"
    )
    assert second.cache_hit is True
    assert second.asset.asset_id == first.asset.asset_id
    # cache_hit is reported, never persisted into the asset's metadata
    assert "cache_hit" not in second.asset.asset_metadata

    different = await registry.store(
        project_id=project.id, asset_type="audio", content=audio + b"x", ext="wav", created_by="test"
    )
    assert different.cache_hit is False
    assert different.asset.asset_id != first.asset.asset_id


@pytest.mark.asyncio
async def test_cache_hit_self_heals_missing_file(db_session, clean_db, tmp_path):
    project = await ProjectRepository(db_session).create(
        name="p", topic="t", duration_seconds=10, aspect_ratio="9:16"
    )
    storage = LocalAssetStorage(str(tmp_path))
    registry = AssetRegistry(db_session, storage=storage)

    stored = await registry.store(
        project_id=project.id, asset_type="audio", content=b"abc", ext="wav", created_by="t"
    )
    (tmp_path / f"{stored.asset.content_hash}.wav").unlink()

    again = await registry.store(
        project_id=project.id, asset_type="audio", content=b"abc", ext="wav", created_by="t"
    )
    assert again.cache_hit is True
    assert registry.read_bytes(again.asset) == b"abc"
