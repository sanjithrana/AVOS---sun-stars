from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.qa import QAResult as QAResultContract
from src.database.models.qa import QACommitteeVerdict, QAResult


class QARepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, shot_id: str, asset_id: UUID, result: QAResultContract) -> QAResult:
        by_dimension = {d.dimension.value: d for d in result.dimensions}

        def score(dim: str) -> float | None:
            d = by_dimension.get(dim)
            return d.score if d else None

        def passed(dim: str) -> bool | None:
            d = by_dimension.get(dim)
            return None if d is None else d.score >= 0.6

        record = QAResult(
            id=uuid4(),
            shot_id=str(shot_id),
            asset_id=asset_id,
            visual_score=score("visual"),
            visual_pass=passed("visual"),
            temporal_score=score("temporal"),
            temporal_pass=passed("temporal"),
            geometry_score=score("geometry"),
            geometry_pass=passed("geometry"),
            identity_score=score("identity"),
            identity_pass=passed("identity"),
            audio_score=score("audio"),
            audio_pass=passed("audio"),
            prompt_adherence_score=score("prompt_adherence"),
            prompt_pass=passed("prompt_adherence"),
            committee_verdict=QACommitteeVerdict(result.status.value),
            diagnostics={d.dimension.value: d.diagnostics for d in result.dimensions},
            confidence=result.confidence,
            evidence=result.evidence,
            evaluated_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_latest_for_shot(self, shot_id: str) -> QAResult | None:
        result = await self.session.execute(
            select(QAResult).where(QAResult.shot_id == str(shot_id)).order_by(QAResult.evaluated_at.desc())
        )
        return result.scalars().first()

    async def list_for_shot(self, shot_id: str) -> list[QAResult]:
        result = await self.session.execute(
            select(QAResult).where(QAResult.shot_id == str(shot_id)).order_by(QAResult.evaluated_at)
        )
        return list(result.scalars().all())
