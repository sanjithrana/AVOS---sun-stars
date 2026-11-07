import pytest
from pydantic import ValidationError

from packages.contracts.experience import ExperienceRecord


def test_valid_experience_is_accepted():
    experience = ExperienceRecord(
        data={
            "publication_outcome": "published",
            "performance": {
                "views": 1000,
            },
        }
    )

    assert experience.data["publication_outcome"] == "published"


def test_non_object_data_is_rejected():
    with pytest.raises(ValidationError):
        ExperienceRecord(data="invalid")


def test_unknown_top_level_field_is_rejected():
    with pytest.raises(ValidationError):
        ExperienceRecord(
            data={},
            project_id="project-001",
        )
