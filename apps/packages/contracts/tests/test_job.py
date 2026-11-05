from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.contracts.job import Job, JobStatus


def valid_job() -> Job:
    now = datetime.now(timezone.utc)

    return Job(
        job_id=uuid4(),
        project_id=uuid4(),
        workflow_id="workflow-001",
        task_type="video_generation",
        status=JobStatus.PENDING,
        payload={},
        retry_count=0,
        created_at=now,
        updated_at=now,
    )


def test_valid_job_is_accepted():
    job = valid_job()

    assert job.status == JobStatus.PENDING
    assert job.retry_count == 0


def test_negative_retry_count_is_rejected():
    with pytest.raises(ValidationError):
        Job(
            job_id=uuid4(),
            project_id=uuid4(),
            workflow_id="workflow-001",
            task_type="video_generation",
            retry_count=-1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


def test_missing_workflow_id_is_rejected():
    with pytest.raises(ValidationError):
        Job(
            job_id=uuid4(),
            project_id=uuid4(),
            task_type="video_generation",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
