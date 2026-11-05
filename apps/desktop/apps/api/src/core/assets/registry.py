import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.storage import LocalAssetStorage, get_storage
from src.database.models.asset import Asset


@dataclass(frozen=True)
class StoredAsset:
    asset: Asset
    cache_hit: bool


class AssetRegistry:
    """
    Content-addressed asset storage (Day 9, AVOS-07 s5).

    store() is idempotent by content: storing identical bytes again
    returns the existing Asset row (cache_hit=True) instead of writing a
    duplicate. cache_hit is returned to the caller rather than written
    into the row's metadata - the first version of this persisted
    "cache_hit": true into the stored asset, so every later read of that
    asset reported a cache hit.
    """

    def __init__(
        self,
        session: AsyncSession,
        storage: LocalAssetStorage | None = None,
    ) -> None:
        self.session = session
        self.storage = storage or get_storage()

    async def store(
        self,
        *,
        project_id: str,
        asset_type: str,
        content: bytes,
        ext: str,
        created_by: str,
        version: int = 1,
        metadata: dict | None = None,
        parent_asset: UUID | None = None,
        source: str = "generated",
    ) -> StoredAsset:
        """parent_asset records lineage (e.g. a Blender depth pass ->
        its physics_proxy). Lineage is fixed at first write: a cache hit
        returns the existing row unchanged."""
        content_hash = hashlib.sha256(content).hexdigest()

        existing = await self.get_by_hash(content_hash)
        if existing is not None:
            # Self-heal: the row exists but the file is gone (e.g. the
            # container was rebuilt without the assets volume).
            if not self.storage.exists(content_hash, ext):
                self.storage.save(content_hash, ext, content)
            # The same bytes made for another project (e.g. the same narration twice): remember that this project
            # uses it too, so per-project lookups (narration for avatar shots, the presenter) still find it.
            meta = dict(existing.asset_metadata or {})
            if meta.get("project_id") != project_id and project_id not in (meta.get("project_ids") or []):
                meta["project_ids"] = [*(meta.get("project_ids") or []), project_id]
                existing.asset_metadata = meta
                await self.session.flush()
            return StoredAsset(asset=existing, cache_hit=True)

        storage_path = self.storage.save(content_hash, ext, content)

        asset = Asset(
            asset_id=uuid4(),
            content_hash=content_hash,
            asset_type=asset_type,
            version=version,
            created_by=created_by,
            source=source,
            parent_asset=parent_asset,
            storage_path=storage_path,
            asset_metadata={
                "project_id": project_id,
                "ext": ext,
                "size_bytes": len(content),
                **(metadata or {}),
            },
        )

        # Shots now generate in parallel: two of them can store the same bytes at the same moment (e.g. the
        # project's presenter portrait). The unique content_hash decides; the loser reuses the winner's row.
        try:
            async with self.session.begin_nested():
                self.session.add(asset)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_by_hash(content_hash)
            if existing is None:
                raise
            return StoredAsset(asset=existing, cache_hit=True)
        await self.session.refresh(asset)

        return StoredAsset(asset=asset, cache_hit=False)

    async def get(self, asset_id: UUID) -> Asset | None:
        result = await self.session.execute(
            select(Asset).where(Asset.asset_id == asset_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, content_hash: str) -> Asset | None:
        result = await self.session.execute(
            select(Asset).where(Asset.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    def read_bytes(self, asset: Asset) -> bytes:
        return self.storage.read(asset.storage_path)
