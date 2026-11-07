from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.contracts.shotspec import ShotSpec, ShotSpecStatus


def valid_shotspec() -> ShotSpec:
    return ShotSpec(
        shot_id=uuid4(),
        shotspec_id=uuid4(),
        version=1,
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
        status=ShotSpecStatus.DRAFT,
        content_hash="abc123",
    )


def test_valid_shotspec_is_accepted():
    shot_spec = valid_shotspec()

    assert shot_spec.version == 1
    assert shot_spec.status == ShotSpecStatus.DRAFT


def test_invalid_version_is_rejected():
    with pytest.raises(ValidationError):
        ShotSpec(
            shot_id=uuid4(),
            shotspec_id=uuid4(),
            version=0,
            created_by=uuid4(),
            created_at=datetime.now(timezone.utc),
            content_hash="abc123",
        )


def test_missing_required_field_is_rejected():
    with pytest.raises(ValidationError):
        ShotSpec(
            shot_id=uuid4(),
            shotspec_id=uuid4(),
            version=1,
            created_by=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
