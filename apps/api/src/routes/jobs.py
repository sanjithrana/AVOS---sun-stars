from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.generation import JobResponse
from src.database.async_session import get_async_db
from src.services.job_service import JobService


router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["jobs"],
)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> JobResponse:
    service = JobService(db)

    return await service.get_job(job_id)
