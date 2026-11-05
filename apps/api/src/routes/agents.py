from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.async_session import get_async_db
from src.repositories.audit_repository import AuditRepository
from src.services.gateway_bridge import trace_entry

router = APIRouter(
    prefix="/api/v1/agents",
    tags=["agents"],
)


class DecisionTraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    agent_decision: str
    tool_name: str
    status: str  # "success" | "error"
    duration_ms: int
    cost: float
    model: str
    error: str | None
    created_at: str


@router.get("/trace", response_model=list[DecisionTraceEntry])
async def get_agent_trace(
    project_id: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
) -> list[DecisionTraceEntry]:
    """
    Real decision trace for a project, read from audit_records - every
    tool call dispatched through gateway_bridge.dispatch_and_audit()
    produces exactly one row here (Day 9 DoD). The frontend's AgentChat
    renders this list live via the SSE events feed appending to it.
    """
    records = await AuditRepository(db).list_for_project(project_id)

    return [DecisionTraceEntry(**trace_entry(record)) for record in records]
