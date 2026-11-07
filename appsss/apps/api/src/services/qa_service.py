"""
QA committee execution (Week 3 Day 14, Engineer 1 side).

Reads what agentic_core.pipelines.qa.committee.evaluate_shot needs
straight from the Asset Registry - the candidate's thumbnail bytes and
the physics proxy's rendered scene layout - so the committee judges the
*actual* generated/rendered artifacts, not a description of them.
Persists one qa_results row per call and moves the shot to PASSED or
FAILED accordingly (never back to QA_PENDING - re-running QA on an
unchanged candidate is expected to reproduce the same verdict, which is
exactly what a deterministic committee should do).
"""

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.pipelines.qa.committee import PhysicsScene, evaluate_shot
from packages.contracts.event import EventType
from packages.contracts.qa import QAStatus
from packages.contracts.shotspec import ShotContent, ShotSpecStatus
from src.core.assets.registry import AssetRegistry
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from packages.contracts.qa_repair_api import (
    QADimensionScoreResponse,
    QAResultResponse,
    RepairPlanResponse,
    ShotQAStateResponse,
)
from src.errors import APIException
from src.repositories.qa_repository import QARepository
from src.repositories.repair_repository import RepairRepository
from src.repositories.shot_repository import ShotRepository
from src.repositories.video_generation_repository import VideoGenerationRepository

_DIMENSION_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("visual", "visual_score", "visual_pass"),
    ("temporal", "temporal_score", "temporal_pass"),
    ("geometry", "geometry_score", "geometry_pass"),
    ("identity", "identity_score", "identity_pass"),
    ("audio", "audio_score", "audio_pass"),
    ("prompt_adherence", "prompt_adherence_score", "prompt_pass"),
)


def qa_result_response(row) -> QAResultResponse:
    """Reconstruct the QADashboard-facing shape from the flattened
    qa_results columns (diagnostics is keyed by dimension, same as
    QARepository.create wrote it). The row has no dedicated "overall
    score" column - it's the mean of the 6 dimension scores, exactly as
    agentic_core.pipelines.qa.committee.evaluate_shot computed it before
    persisting, so it's recomputed the same way here."""
    dimensions = []
    scores: list[float] = []
    for dimension, score_col, _pass_col in _DIMENSION_FIELDS:
        score = getattr(row, score_col)
        if score is None:
            continue
        scores.append(float(score))
        dimensions.append(
            QADimensionScoreResponse(
                dimension=dimension,
                score=float(score),
                confidence=float(row.confidence) if row.confidence is not None else None,
                diagnostics=(row.diagnostics or {}).get(dimension, {}),
            )
        )
    return QAResultResponse(
        id=row.id,
        shot_id=row.shot_id,
        status=row.committee_verdict.value,
        score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        confidence=float(row.confidence) if row.confidence is not None else None,
        evidence=row.evidence or {},
        dimensions=dimensions,
        evaluated_at=row.evaluated_at,
    )


def repair_plan_response(row) -> RepairPlanResponse:
    return RepairPlanResponse(
        id=row.id,
        shot_id=row.shot_id,
        attempt=row.attempt,
        rung=row.rung,
        failure_type=row.failure_type,
        target_stage=row.target_stage,
        changes=row.changes,
        preserve=row.preserve,
        applied_at=row.applied_at,
        resulting_asset_id=row.resulting_asset_id,
    )


async def shot_qa_state(qa_repo: QARepository, repair_repo: RepairRepository, shot_id: str) -> ShotQAStateResponse:
    latest = await qa_repo.get_latest_for_shot(shot_id)
    repairs = await repair_repo.list_for_shot(shot_id)
    return ShotQAStateResponse(
        shot_id=shot_id,
        latest_result=qa_result_response(latest) if latest else None,
        repairs=[repair_plan_response(r) for r in repairs],
    )


class QAServiceError(RuntimeError):
    """The shot/version has nothing yet for the committee to judge."""


class QACommitteeService:
    def __init__(self, session: AsyncSession, *, registry: AssetRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or AssetRegistry(session)
        self.shots = ShotRepository(session)
        self.generations = VideoGenerationRepository(session)
        self.qa = QARepository(session)

    async def run(
        self,
        shot_id: str,
        *,
        candidate_index: int = 0,
        version: int | None = None,
        force_fail: bool = False,
    ) -> dict[str, Any]:
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise APIException(code="not_found", message="Shot not found.", status_code=404)
        row = await self.shots.get_version(shot.id, version or shot.current_version)
        if row is None:
            raise APIException(code="not_found", message="Shot version not found.", status_code=404)

        generation = await self.generations.get_latest_for_shot(shot.id, row.version)
        if generation is None or not generation.candidates:
            raise QAServiceError(
                f"Shot {shot.shot_index + 1} v{row.version} has no generated candidates yet; "
                "run the Video agent (generate_video_shot) first."
            )
        try:
            candidate = generation.candidates[candidate_index]
        except IndexError as exc:
            raise QAServiceError(
                f"Shot {shot.shot_index + 1} has only {len(generation.candidates)} candidates; "
                f"candidate_index {candidate_index} does not exist."
            ) from exc

        thumbnail_asset = await self.registry.get(UUID(candidate["thumbnail_asset_id"]))
        if thumbnail_asset is None:
            raise QAServiceError("The candidate's thumbnail asset is missing from the registry.")
        thumbnail_bytes = self.registry.read_bytes(thumbnail_asset)

        if row.physics_proxy_asset_id is None:
            raise QAServiceError("This version has no physics proxy; the Blender stage never completed.")
        proxy_asset = await self.registry.get(row.physics_proxy_asset_id)
        if proxy_asset is None:
            raise QAServiceError("The physics proxy asset is missing from the registry.")
        proxy_doc = json.loads(self.registry.read_bytes(proxy_asset))
        scene_doc = proxy_doc.get("scene", {})
        scene = PhysicsScene(
            width=int(proxy_doc["width"]),
            height=int(proxy_doc["height"]),
            subject_box=tuple(scene_doc.get("subject_box", [0, 0, proxy_doc["width"], proxy_doc["height"]])),
        )

        content = ShotContent.model_validate(row.content)
        result = evaluate_shot(
            shot_id=shot.id,
            video_asset_id=candidate["asset_id"],
            content=content,
            scene=scene,
            thumbnail_bytes=thumbnail_bytes,
            thumbnail_size=(64, 36),           # the mock placeholder frame
            force_fail=force_fail,
            expected_aspect=await self._aspect(shot.project_id),
        )

        record = await self.qa.create(shot.id, thumbnail_asset.asset_id, result)
        if not force_fail:   # the router learns which model / GPU gives results that pass
            from src.services.fabric_service import record_qa

            await record_qa(self.session, shot.id, row.version, result.score)

        new_status = ShotSpecStatus.PASSED if result.status == QAStatus.PASS else ShotSpecStatus.FAILED
        await self.shots.set_version_status(shot, row, new_status.value)

        queue_event(
            self.session,
            make_event(
                event_type=EventType.QA_PASSED if result.status == QAStatus.PASS else EventType.QA_FAILED,
                project_id=shot.project_id,
                payload={
                    "shot_id": shot.id,
                    "version": row.version,
                    "qa_result_id": str(record.id),
                    "status": result.status.value,
                    "score": result.score,
                    "failing_dimensions": result.evidence.get("failing_dimensions", []),
                    "forced": force_fail,
                },
            ),
        )

        return {
            "qa_result_id": str(record.id),
            "shot_id": shot.id,
            "version": row.version,
            "status": result.status.value,
            "score": result.score,
            "confidence": result.confidence,
            "dimensions": [d.model_dump(mode="json") for d in result.dimensions],
            "evidence": result.evidence,
        }

    async def _aspect(self, project_id: str) -> float | None:
        from src.repositories.project_repository import ProjectRepository

        project = await ProjectRepository(self.session).get(project_id)
        w, h = (int(x) for x in (getattr(project, "aspect_ratio", None) or "9:16").split(":"))
        return w / h

    # -- Gateway executor (QA agent) ---------------------------------------

    async def tool_run_qa_committee(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.run(
            arguments["shot_id"],
            candidate_index=arguments.get("candidate_index", 0),
            force_fail=arguments.get("force_fail", False),
        )
        return {**summary, "model": "qa-committee:2-real+4-placeholder"}
