import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import EventType
from packages.contracts.human_gate import HumanGateStatus, HumanGateType
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, queue_event
from src.database.base import utcnow
from src.database.models.human_gate import HumanGate
from src.domain.projects.status import ProjectStatus
from src.errors import APIException
from src.repositories.human_gate_repository import HumanGateRepository
from src.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)

# Signal name must match CreateVideoWorkflow.gate_decided.
GATE_DECIDED_SIGNAL = "gate_decided"


class HumanGateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = HumanGateRepository(session)
        self.projects = ProjectRepository(session)

    async def get(self, gate_id: UUID) -> HumanGate:
        gate = await self.repository.get(gate_id)
        if gate is None:
            raise APIException(code="not_found", message="Gate not found.", status_code=404)
        return gate

    async def get_pending_for_project(
        self, project_id: str, gate_type: str | None = None
    ) -> HumanGate | None:
        return await self.repository.get_pending_for_project(project_id, gate_type)

    async def list_for_project(self, project_id: str) -> list[HumanGate]:
        return await self.repository.list_for_project(project_id)

    async def decide(
        self,
        gate_id: UUID,
        *,
        approve: bool,
        decided_by: str,
        comment: str | None,
    ) -> HumanGate:
        # Row lock: two concurrent approve/reject clicks can't both see
        # "pending" and both win.
        result = await self.session.execute(
            select(HumanGate).where(HumanGate.id == gate_id).with_for_update()
        )
        gate = result.scalar_one_or_none()

        if gate is None:
            raise APIException(code="not_found", message="Gate not found.", status_code=404)

        if gate.status != HumanGateStatus.PENDING.value:
            raise APIException(
                code="conflict",
                message=f"Gate is already '{gate.status}', not pending.",
                project_id=gate.project_id,
                status_code=409,
            )

        gate.status = (
            HumanGateStatus.APPROVED.value if approve else HumanGateStatus.REJECTED.value
        )
        gate.decided_by = decided_by
        gate.comment = comment
        gate.decided_at = utcnow()

        new_project_status = (
            (ProjectStatus.RENDERING_VIDEO if gate.gate_type == HumanGateType.FINAL_APPROVAL.value
             else ProjectStatus.GENERATING_AUDIO) if approve else ProjectStatus.REJECTED
        )
        await self.projects.set_status(gate.project_id, new_project_status.value)

        queue_event(
            self.session,
            make_event(
                event_type=EventType.HUMAN_GATE_DECIDED,
                project_id=gate.project_id,
                payload={
                    "gate_id": str(gate.id),
                    "gate_type": gate.gate_type,
                    "status": gate.status,
                    "decided_by": decided_by,
                },
            ),
        )
        if approve and gate.gate_type == HumanGateType.SCRIPT_APPROVAL.value:
            queue_event(
                self.session,
                make_event(
                    event_type=EventType.SCRIPT_APPROVED,
                    project_id=gate.project_id,
                    payload={"gate_id": str(gate.id)},
                ),
            )
        queue_event(
            self.session,
            make_event(
                event_type=EventType.PROJECT_STATUS_CHANGED,
                project_id=gate.project_id,
                payload={"status": new_project_status.value},
            ),
        )

        await commit_and_publish(self.session)
        await self.session.refresh(gate)

        if gate.workflow_id:
            await self._signal_workflow(gate.workflow_id, approve)

        return gate

    async def _signal_workflow(self, workflow_id: str, approve: bool) -> None:
        """Resume the CreateVideoWorkflow paused on this gate.

        The decision is already committed, so a Temporal hiccup must not
        turn it into a 500. Signals are durable once accepted; if the
        call itself fails we log it (the workflow can be re-signalled
        with the same value).
        """
        from src.temporal.client import get_client

        try:
            client = await get_client()
            handle = client.get_workflow_handle(workflow_id)
            await handle.signal(GATE_DECIDED_SIGNAL, approve)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to signal workflow %s (approve=%s)", workflow_id, approve)
