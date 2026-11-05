from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.contracts.asset import Asset, AssetLifecycleState


def valid_asset() -> Asset:
    return Asset(
        asset_id=uuid4(),
        content_hash="hash-123",
        asset_type="video_shot",
        version=1,
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
        source="comfyui",
        storage_uri="s3://solunex/assets/video.mp4",
        metadata={},
        lifecycle_state=AssetLifecycleState.CREATED,
    )


def test_valid_asset_is_accepted():
    asset = valid_asset()

    assert asset.version == 1
    assert asset.lifecycle_state == AssetLifecycleState.CREATED


def test_invalid_version_is_rejected():
    with pytest.raises(ValidationError):
        Asset(
            asset_id=uuid4(),
            content_hash="hash-123",
            asset_type="video_shot",
            version=0,
            created_by=uuid4(),
            created_at=datetime.now(timezone.utc),
            source="comfyui",
            storage_uri="s3://solunex/assets/video.mp4",
        )


def test_missing_content_hash_is_rejected():
    with pytest.raises(ValidationError):
        Asset(
            asset_id=uuid4(),
            asset_type="video_shot",
            version=1,
            created_by=uuid4(),
            created_at=datetime.now(timezone.utc),
            source="comfyui",
            storage_uri="s3://solunex/assets/video.mp4",
        )
