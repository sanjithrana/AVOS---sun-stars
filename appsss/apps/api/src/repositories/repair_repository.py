from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.repair import RepairPlan


class RepairRepository:
    """Repair ladder persistence. count_for_shot() *is* the durable
    attempt counter (AVOS-03 v1.1 s14.6) - there is no in-memory state
    to lose on a restart, because the next attempt number is always
    (rows already committed for this shot) + 1, read fresh every call."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_for_shot(self, shot_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(RepairPlan).where(RepairPlan.shot_id == str(shot_id))
        )
        return int(result.scalar_one())

    async def create(
        self,
        *,
        shot_id: str,
        qa_result_id: UUID,
        failure_type: str,
        target_stage: str,
        changes: dict,
        preserve: list[str],
        attempt: int,
        rung: str,
    ) -> RepairPlan:
        record = RepairPlan(
            id=uuid4(),
            shot_id=str(shot_id),
            qa_result_id=qa_result_id,
            failure_type=failure_type,
            target_stage=target_stage,
            changes=changes,
            preserve=preserve,
            attempt=attempt,
            rung=rung,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def mark_applied(self, plan: RepairPlan, *, resulting_asset_id: UUID | None) -> None:
        plan.applied_at = datetime.now(timezone.utc)
        plan.resulting_asset_id = resulting_asset_id
        await self.session.flush()

    async def list_for_shot(self, shot_id: str) -> list[RepairPlan]:
        result = await self.session.execute(
            select(RepairPlan).where(RepairPlan.shot_id == str(shot_id)).order_by(RepairPlan.attempt)
        )
        return list(result.scalars().all())
