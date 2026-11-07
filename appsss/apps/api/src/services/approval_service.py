"""
Stubbed final gate (Week 3 Day 15 - AVOS-18 s6.3's last step, "Approve
the repaired/passing shots").

Final Assembly/FFmpeg (stitching approved shots into one rendered video)
doesn't exist yet - that's a Week 4+ ticket (see RUNBOOK.md). Until then,
"approve" *is* the final stage: a human sign-off that a QA-PASSED shot is
done, recorded the same audited way as every other decision in the
pipeline (Tool Gateway -> dispatch_and_audit -> one audit_records row ->
SHOT_APPROVED event), not a silent status flip. A shot can only be
approved once its *current* version's latest QA result is a genuine
PASS - repaired shots go through this the same way a first-try PASS
does, since by the time a repair lands the shot back in QA_PENDING and
a fresh committee pass gives it PASSED, there is no difference left to
this gate between "passed first try" and "passed after repair".
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import EventType
from packages.contracts.shotspec import ShotSpecStatus
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.errors import APIException
from src.repositories.qa_repository import QARepository
from src.repositories.shot_repository import ShotRepository


class ApprovalServiceError(RuntimeError):
    """The shot isn't in a state the final gate can approve."""


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.shots = ShotRepository(session)
        self.qa = QARepository(session)

    async def approve(self, shot_id: str) -> dict[str, Any]:
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise APIException(code="not_found", message="Shot not found.", status_code=404)

        current = await self.shots.get_version(shot.id, shot.current_version)
        if current is None:
            raise APIException(code="not_found", message="Shot version not found.", status_code=404)

        if current.status == ShotSpecStatus.APPROVED.value:
            raise ApprovalServiceError(f"Shot {shot.shot_index + 1} is already approved.")

        qa_row = await self.qa.get_latest_for_shot(shot.id)
        if qa_row is None or qa_row.committee_verdict.value != "PASS":
            raise ApprovalServiceError(
                f"Shot {shot.shot_index + 1} has no passing QA result to approve; "
                "run the QA committee (and repair, if it failed) first."
            )

        await self.shots.set_version_status(shot, current, ShotSpecStatus.APPROVED.value)

        queue_event(
            self.session,
            make_event(
                event_type=EventType.SHOT_APPROVED,
                project_id=shot.project_id,
                payload={"shot_id": shot.id, "version": current.version, "qa_result_id": str(qa_row.id)},
            ),
        )

        return {
            "shot_id": shot.id,
            "version": current.version,
            "status": ShotSpecStatus.APPROVED.value,
            "qa_result_id": str(qa_row.id),
        }

    # -- Gateway executor (Director: "approval" scope) ---------------------

    async def tool_approve_shot(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.approve(arguments["shot_id"])
        return {**summary, "model": "final-gate:stub"}
