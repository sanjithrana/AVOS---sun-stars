from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.human_gate import HumanGateDecision, HumanGateResponse
from src.database.async_session import get_async_db
from src.services.human_gate_service import HumanGateService

router = APIRouter(
    prefix="/api/v1/gates",
    tags=["gates"],
)


@router.get("/{gate_id}", response_model=HumanGateResponse)
async def get_gate(
    gate_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> HumanGateResponse:
    gate = await HumanGateService(db).get(gate_id)
    return HumanGateResponse.model_validate(gate)


@router.post("/{gate_id}/approve", response_model=HumanGateResponse)
async def approve_gate(
    gate_id: UUID,
    decision: HumanGateDecision,
    db: AsyncSession = Depends(get_async_db),
) -> HumanGateResponse:
    gate = await HumanGateService(db).decide(
        gate_id,
        approve=True,
        decided_by=decision.decided_by,
        comment=decision.comment,
    )
    return HumanGateResponse.model_validate(gate)


@router.post("/{gate_id}/reject", response_model=HumanGateResponse)
async def reject_gate(
    gate_id: UUID,
    decision: HumanGateDecision,
    db: AsyncSession = Depends(get_async_db),
) -> HumanGateResponse:
    gate = await HumanGateService(db).decide(
        gate_id,
        approve=False,
        decided_by=decision.decided_by,
        comment=decision.comment,
    )
    return HumanGateResponse.model_validate(gate)
