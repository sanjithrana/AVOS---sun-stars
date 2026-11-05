import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.common import UUIDStr
from src.core.assets.registry import AssetRegistry
from src.database.async_session import get_async_db
from src.errors import APIException

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

MEDIA_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "json": "application/json",
    "mp4": "video/mp4",
    "webm": "video/webm",
}


class AssetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUIDStr
    content_hash: str
    asset_type: str
    version: int
    created_by: str
    source: str
    parent_asset: UUIDStr | None = None  # lineage (e.g. blender_depth -> physics_proxy)
    metadata: dict


async def _get_asset(db: AsyncSession, asset_id: UUID):
    asset = await AssetRegistry(db).get(asset_id)
    if asset is None:
        raise APIException(code="not_found", message="Asset not found.", status_code=404)
    return asset


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: UUID, db: AsyncSession = Depends(get_async_db)) -> AssetResponse:
    asset = await _get_asset(db, asset_id)
    return AssetResponse(
        asset_id=asset.asset_id,
        content_hash=asset.content_hash,
        asset_type=asset.asset_type,
        version=asset.version,
        created_by=asset.created_by,
        source=asset.source,
        parent_asset=asset.parent_asset,
        metadata=asset.asset_metadata,
    )


@router.get("/{asset_id}/content")
async def get_asset_content(
    asset_id: UUID,
    download: str | None = None,
    db: AsyncSession = Depends(get_async_db),
) -> FileResponse:
    """Stream the stored file (narration audio, final MP4...) to the UI.
    Supports HTTP range requests, so the video player can seek.
    ?download=<filename> serves it as an attachment with that name."""
    asset = await _get_asset(db, asset_id)
    from src.core.assets.storage import get_storage

    try:
        local = get_storage().local_path(asset.storage_path)   # S3 / MinIO assets are fetched into the cache first
    except Exception:  # noqa: BLE001
        local = None
    if local is None:
        raise APIException(code="not_found", message="Asset file missing on disk.", status_code=404)
    ext = asset.storage_path.rsplit(".", 1)[-1].lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
    if download:
        name = re.sub(r"[^A-Za-z0-9._ -]+", "", download).strip() or f"avos-{asset_id}"
        if not name.lower().endswith(f".{ext}"):
            name = f"{name}.{ext}"
        return FileResponse(local, media_type=media_type, filename=name)
    return FileResponse(local, media_type=media_type)
