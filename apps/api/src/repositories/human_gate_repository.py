from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.human_gate import HumanGate


class HumanGateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: str,
        gate_type: str,
        payload: dict,
        workflow_id: str | None = None,
    ) -> HumanGate:
        gate = HumanGate(
            id=uuid4(),
            project_id=project_id,
            gate_type=gate_type,
            status="pending",
            payload=payload,
            workflow_id=workflow_id,
            created_at=datetime.now(timezone.utc),
        )

        self.session.add(gate)
        await self.session.flush()
        await self.session.refresh(gate)

        return gate

    async def get_for_workflow(
        self,
        workflow_id: str,
        gate_type: str,
    ) -> HumanGate | None:
        """Existing gate opened by this workflow run, if any. Lets a
        retried Temporal activity reuse its gate instead of opening a
        duplicate."""
        result = await self.session.execute(
            select(HumanGate)
            .where(
                HumanGate.workflow_id == workflow_id,
                HumanGate.gate_type == gate_type,
            )
            .order_by(HumanGate.created_at.desc())
        )
        return result.scalars().first()

    async def list_for_project(
        self,
        project_id: str,
        gate_type: str | None = None,
    ) -> list[HumanGate]:
        query = select(HumanGate).where(HumanGate.project_id == project_id)
        if gate_type:
            query = query.where(HumanGate.gate_type == gate_type)
        result = await self.session.execute(
            query.order_by(HumanGate.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, gate_id: UUID) -> HumanGate | None:
        result = await self.session.execute(
            select(HumanGate).where(HumanGate.id == gate_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_for_project(
        self,
        project_id: str,
        gate_type: str | None = None,
    ) -> HumanGate | None:
        query = select(HumanGate).where(
            HumanGate.project_id == project_id,
            HumanGate.status == "pending",
        )
        if gate_type:
            query = query.where(HumanGate.gate_type == gate_type)

        result = await self.session.execute(query.order_by(HumanGate.created_at.desc()))
        return result.scalars().first()

    async def decide(
        self,
        gate_id: UUID,
        *,
        status: str,
        decided_by: str,
        comment: str | None,
    ) -> HumanGate | None:
        gate = await self.get(gate_id)

        if gate is None:
            return None

        gate.status = status
        gate.decided_by = decided_by
        gate.comment = comment
        gate.decided_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(gate)

        return gate
