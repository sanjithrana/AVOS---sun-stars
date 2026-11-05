"""
Repair ladder execution (Week 3 Day 14, Engineer 1 + Engineer 2 handoff).

agentic_core.agents.repair.classifier owns the pure decision (which
attempt -> which rung -> what changes); this service owns the durable
state and the actual work:

  1. attempt = RepairRepository.count_for_shot(shot_id) + 1 - read fresh
     from Postgres every call, never cached on this object or anywhere
     else, so a killed-and-restarted worker resumes with the exact same
     next attempt number (AVOS-03 v1.1 s14.6's durability requirement,
     proven directly by api/tests/test_repair_ladder.py).
  2. persist the RepairPlan the classifier produced.
  3. MICRO/MACRO: actually apply it - regenerate the shot's candidates
     (through the same audited, idempotent VideoGenerationService as
     Day 13, with a fresh idempotency key and a seed/prompt nudge scoped
     to the rung) and put the version back in QA_PENDING for another
     committee pass.
  4. HUMAN_REQUIRED: apply nothing automatically. The version moves to
     REPAIRING and stays there until a human acts (out of scope this
     week) - there is no rung past this one to escalate to.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.agents.repair.classifier import build_repair_plan
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.event import EventType
from packages.contracts.qa import QADimension, QADimensionResult, QAResult as QAResultContract, QAStatus
from packages.contracts.shotspec import ShotSpecStatus
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.errors import APIException
from src.repositories.qa_repository import QARepository
from src.repositories.project_repository import ProjectRepository
from src.repositories.repair_repository import RepairRepository
from src.repositories.shot_repository import ShotRepository
from src.services.gateway_bridge import dispatch_and_audit
from src.services.video_generation_service import VideoGenerationService

_DIMENSION_COLUMNS: tuple[tuple[str, QADimension], ...] = (
    ("visual_score", QADimension.VISUAL),
    ("temporal_score", QADimension.TEMPORAL),
    ("geometry_score", QADimension.GEOMETRY),
    ("identity_score", QADimension.IDENTITY),
    ("audio_score", QADimension.AUDIO),
    ("prompt_adherence_score", QADimension.PROMPT_ADHERENCE),
)


class RepairServiceError(RuntimeError):
    """Repair was requested for a shot with nothing to repair, or that
    already has no rung left to apply automatically."""


def _qa_contract_from_row(qa_row) -> QAResultContract:
    """Reconstruct enough of the Pydantic QAResult for the pure
    classifier (it only reads .status and each dimension's .score) from
    the flattened qa_results columns."""
    dimensions = [
        QADimensionResult(dimension=dim, score=float(getattr(qa_row, column)))
        for column, dim in _DIMENSION_COLUMNS
        if getattr(qa_row, column) is not None
    ]
    return QAResultContract(
        shot_id=qa_row.shot_id,
        video_asset_id=qa_row.asset_id,
        status=QAStatus(qa_row.committee_verdict.value),
        score=float(qa_row.visual_score or 0),
        confidence=float(qa_row.confidence) if qa_row.confidence is not None else None,
        evidence=qa_row.evidence or {},
        dimensions=dimensions,
    )


class RepairService:
    def __init__(self, session: AsyncSession, *, video: VideoGenerationService | None = None) -> None:
        self.session = session
        self.shots = ShotRepository(session)
        self.qa = QARepository(session)
        self.repairs = RepairRepository(session)
        self.video = video or VideoGenerationService(session)

    async def repair(self, shot_id: str) -> dict[str, Any]:
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise APIException(code="not_found", message="Shot not found.", status_code=404)

        qa_row = await self.qa.get_latest_for_shot(shot.id)
        if qa_row is None or qa_row.committee_verdict.value != "FAIL":
            raise RepairServiceError(
                f"Shot {shot.shot_index + 1} has no failing QA result to repair; run the QA committee first."
            )
        current = await self.shots.get_version(shot.id, shot.current_version)
        if current is None:
            raise APIException(code="not_found", message="Shot version not found.", status_code=404)

        attempt = await self.repairs.count_for_shot(shot.id) + 1
        from agentic_core.model_fabric import policy as fabric_policy

        project = await ProjectRepository(self.session).get(shot.project_id)
        limits = fabric_policy.resolve(getattr(project, "generation_policy", None))
        plan = build_repair_plan(_qa_contract_from_row(qa_row), attempt=attempt, max_attempts=limits.max_attempts)

        record = await self.repairs.create(
            shot_id=shot.id,
            qa_result_id=qa_row.id,
            failure_type=plan["failure"],
            target_stage=plan["target"],
            changes=plan["changes"],
            preserve=plan["preserve"],
            attempt=attempt,
            rung=plan["rung"],
        )

        if plan["rung"] == "HUMAN_REQUIRED":
            await self.shots.set_version_status(shot, current, ShotSpecStatus.REPAIRING.value)
            await self.repairs.mark_applied(record, resulting_asset_id=None)
            queue_event(
                self.session,
                make_event(
                    event_type=EventType.REPAIR_ESCALATED,
                    project_id=shot.project_id,
                    payload={"shot_id": shot.id, "attempt": attempt, "rung": plan["rung"]},
                ),
            )
            return self._summary(shot, current, record, applied=False)

        result = await dispatch_and_audit(
            self.session,
            project_id=shot.project_id,
            role=AgentRole.VIDEO_AGENT,
            tool_name="generate_video_shot",
            tool_input={
                "shot_id": shot.id,
                "physics_proxy_asset_id": str(current.physics_proxy_asset_id),
                "idempotency_key": f"{shot.id}:{current.version}:repair:{attempt}",
            },
            executor=lambda arguments: self.video.generate(
                arguments["shot_id"],
                physics_proxy_asset_id=arguments["physics_proxy_asset_id"],
                idempotency_key=arguments["idempotency_key"],
                seed_offset=plan["changes"].get("seed_offset", 0),
                prompt_suffix=plan["changes"].get("prompt_suffix"),
            ),
            agent_decision=(
                f"Repair agent: attempt {attempt} ({plan['rung']}) for shot {shot.shot_index + 1} - "
                f"{plan['failure']}. {plan['changes'].get('note', '')}"
            ),
        )
        # Back in QA_PENDING: fresh candidates await another committee
        # pass. generate() only advances status automatically from
        # BLENDER_READY/GENERATING - this version is FAILED, so it's
        # advanced explicitly here instead.
        await self.shots.set_version_status(shot, current, ShotSpecStatus.QA_PENDING.value)
        await self.repairs.mark_applied(record, resulting_asset_id=result.result["asset_id"])

        queue_event(
            self.session,
            make_event(
                event_type=EventType.REPAIR_STARTED,
                project_id=shot.project_id,
                payload={
                    "shot_id": shot.id,
                    "attempt": attempt,
                    "rung": plan["rung"],
                    "video_generation_id": result.result["video_generation_id"],
                },
            ),
        )
        return self._summary(shot, current, record, applied=True)

    @staticmethod
    def _summary(shot, version, record, *, applied: bool) -> dict[str, Any]:
        return {
            "repair_plan_id": str(record.id),
            "shot_id": shot.id,
            "attempt": record.attempt,
            "rung": record.rung,
            "failure": record.failure_type,
            "target": record.target_stage,
            "changes": record.changes,
            "preserve": record.preserve,
            "applied": applied,
            "status": version.status,
        }

    # -- Gateway executor (Repair agent) -----------------------------------

    async def tool_repair_shot(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.repair(arguments["shot_id"])
        return {**summary, "model": "repair-controller:ladder"}
