from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import utcnow
from src.database.models.audit import AuditRecord


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: str,
        agent_decision: str,
        tool_name: str,
        tool_call_input: dict,
        tool_result: dict,
        duration_ms: int,
        cost: float,
        model: str,
        input_hash: str,
        output_hash: str,
        error: str | None = None,
        retry_count: int = 0,
    ) -> AuditRecord:
        record = AuditRecord(
            id=uuid4(),
            project_id=project_id,
            agent_decision=agent_decision,
            tool_name=tool_name,
            tool_call_input=tool_call_input,
            tool_result=tool_result,
            duration_ms=duration_ms,
            cost=cost,
            model=model,
            input_hash=input_hash,
            output_hash=output_hash,
            error=error,
            retry_count=retry_count,
            created_at=utcnow(),
        )

        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)

        return record

    async def list_for_project(
        self,
        project_id: str,
        limit: int = 100,
    ) -> list[AuditRecord]:
        result = await self.session.execute(
            select(AuditRecord)
            .where(AuditRecord.project_id == project_id)
            .order_by(AuditRecord.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
