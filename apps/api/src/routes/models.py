"""GET /api/v1/models: the AVOS model catalog with what is ready to use right now (the Models page)."""
from typing import Any

from fastapi import APIRouter

from agentic_core.models import catalog

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
async def list_models() -> dict[str, Any]:
    from agentic_core.model_fabric import workers

    await workers.statuses()   # so models your GPU workers can run show as ready
    return catalog.status()
