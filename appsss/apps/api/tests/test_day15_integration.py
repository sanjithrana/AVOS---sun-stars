"""
Week 3 Day 15 - the integration checkpoint's two new pieces, proven the
same way Day 13/14 proved theirs: real Postgres, the real audited
Gateway path (dispatch_and_audit), no direct DB seeding for the parts
that can go through the real API instead.

1. force_fail on run_qa_committee: the mock Video generator and the
   geometry QA dimension share the same SHOT_TYPE_SCALE mapping
   (agentic_core/pipelines/qa/committee.py), so a mock-generated shot
   always earns a genuine PASS - there is no naturally-occurring FAIL in
   this stack to drive the repair ladder with. force_fail runs the real
   evaluation and then deliberately, visibly overrides it, so the whole
   FAIL -> repair -> escalate chain in test_repair_ladder.py can also be
   driven through the live QA endpoint end to end, not only from a
   seeded qa_results row.
2. The stubbed final gate (approve_shot): only a shot whose current
   version's latest QA result is PASS may be approved; already-approved
   is rejected; and only the Director's "approval" tool scope may call
   it, same permission enforcement as every other tool.
"""

import pytest
from sqlalchemy import select

from agentic_core.tool_gateway.gateway import ToolPermissionDeniedError
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.shotspec import ShotContent
from src.core.assets.registry import AssetRegistry
from src.core.assets.storage import LocalAssetStorage
from src.core.blender.client import MockBlenderClient
from src.database.models.audit import AuditRecord
from src.database.models.repair import RepairPlan
from src.repositories.project_repository import ProjectRepository
from src.repositories.qa_repository import QARepository
from src.repositories.shot_repository import ShotRepository
from src.services.approval_service import ApprovalService, ApprovalServiceError
from src.services.blender_stage_service import BlenderStageService
from src.services.gateway_bridge import dispatch_and_audit
from src.services.qa_service import QACommitteeService, QAServiceError
from src.services.repair_service import RepairService
from src.services.shotspec_service import ShotSpecService
from src.services.video_generation_service import VideoGenerationService
from tests.conftest import requires_db

pytestmark = requires_db


def _content() -> ShotContent:
    return ShotContent(
        beat_label="beat_1", start_time=0.0, end_time=3.0, narration="A character waves.",
        description="A cheerful character waves at the camera.",
        style="bright, friendly storybook illustration",
        environment={"location": "main setting", "time_of_day": "morning", "weather": "clear"},
    )


async def _generated_shot(session, tmp_path):
    project = await ProjectRepository(session).create(
        name="Day 15 checkpoint", topic="Flowers", duration_seconds=6, aspect_ratio="9:16"
    )
    specs = ShotSpecService(session)
    shot, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=0)
    await specs.validate_shot_spec(shot.id)
    await session.commit()

    registry = AssetRegistry(session, storage=LocalAssetStorage(str(tmp_path)))
    stage = BlenderStageService(session, client=MockBlenderClient(), registry=registry)
    blender = await dispatch_and_audit(
        session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    proxy_id = blender.result["physics_proxy_asset_id"]

    video = VideoGenerationService(session, registry=registry)
    await dispatch_and_audit(
        session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot.id, "physics_proxy_asset_id": proxy_id},
        executor=video.tool_generate_video_shot, agent_decision="x",
    )
    await session.commit()
    return project, shot, registry


# -- force_fail --------------------------------------------------------


@pytest.mark.asyncio
async def test_force_fail_overrides_a_genuine_pass_visibly(db_session, clean_db, captured_events, tmp_path):
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    qa = QACommitteeService(db_session, registry=registry)

    # Without force_fail, the mock pipeline agrees with itself and PASSES
    # (this is the "by construction" fact the Day 15 runbook note explains).
    baseline = await qa.run(shot.id)
    assert baseline["status"] == "PASS"

    # A second shot, forced: the real evaluation still runs (both real
    # dimensions are computed), but the verdict is deliberately, visibly
    # flipped to FAIL.
    specs = ShotSpecService(db_session)
    shot2, _, _ = await specs.create_shot_spec(project.id, _content(), shot_index=1)
    await specs.validate_shot_spec(shot2.id)
    await db_session.commit()
    stage = BlenderStageService(db_session, client=MockBlenderClient(), registry=registry)
    blender2 = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.PHYSICS_AGENT, tool_name="run_blender_proxy",
        tool_input={"shot_id": shot2.id}, executor=stage.tool_run_blender_proxy, agent_decision="x",
    )
    video = VideoGenerationService(db_session, registry=registry)
    await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.VIDEO_AGENT, tool_name="generate_video_shot",
        tool_input={"shot_id": shot2.id, "physics_proxy_asset_id": blender2.result["physics_proxy_asset_id"]},
        executor=video.tool_generate_video_shot, agent_decision="x",
    )
    await db_session.commit()

    forced = await qa.run(shot2.id, force_fail=True)
    assert forced["status"] == "FAIL"
    assert forced["evidence"]["forced"] is True
    assert set(forced["evidence"]["failing_dimensions"]) == {"visual", "geometry"}
    forced_dims = {d["dimension"]: d for d in forced["dimensions"]}
    assert forced_dims["visual"]["score"] == 0.0
    assert forced_dims["geometry"]["score"] == 0.0
    assert forced_dims["visual"]["diagnostics"]["forced"] is True
    # The real score is preserved alongside the forced one - nothing
    # about the override is silent.
    assert forced_dims["geometry"]["diagnostics"]["original_score"] > 0.6

    row = await QARepository(db_session).get_latest_for_shot(shot2.id)
    assert row.committee_verdict.value == "FAIL"


@pytest.mark.asyncio
async def test_force_fail_through_the_live_gateway_drives_the_repair_ladder_to_escalation(
    db_session, clean_db, captured_events, tmp_path
):
    """The Day 15 EOD checklist's own words: "force at least one shot to
    FAIL on purpose to prove the repair ladder fires ... and escalates
    correctly [on] 3 attempts" - driven entirely through the real
    dispatch_and_audit path (QA -> repair -> QA -> repair -> QA ->
    repair), the same one the live UI and the run_qa_committee /
    repair_shot HTTP routes use. No qa_results row is ever seeded by
    hand."""
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    qa_service = QACommitteeService(db_session, registry=registry)
    repair = RepairService(db_session, video=VideoGenerationService(db_session, registry=registry))

    async def run_qa(force: bool) -> dict:
        result = await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.QA_AGENT, tool_name="run_qa_committee",
            tool_input={"shot_id": shot.id, "candidate_index": 0, "force_fail": force},
            executor=qa_service.tool_run_qa_committee, agent_decision="x",
        )
        return result.result

    async def run_repair() -> dict:
        result = await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.REPAIR_AGENT, tool_name="repair_shot",
            tool_input={"shot_id": shot.id}, executor=repair.tool_repair_shot, agent_decision="x",
        )
        return result.result

    # Attempt 1: force a FAIL -> MICRO repair (regenerates, back to QA_PENDING).
    first_qa = await run_qa(force=True)
    assert first_qa["status"] == "FAIL"
    attempt1 = await run_repair()
    assert (attempt1["attempt"], attempt1["rung"], attempt1["status"]) == (1, "MICRO", "QA_PENDING")

    # Attempt 2: force it to fail again (the regenerated mock candidate
    # would otherwise PASS again by construction) -> MACRO repair.
    second_qa = await run_qa(force=True)
    assert second_qa["status"] == "FAIL"
    attempt2 = await run_repair()
    assert (attempt2["attempt"], attempt2["rung"], attempt2["status"]) == (2, "MACRO", "QA_PENDING")

    # Attempt 3: force it to fail a third time -> escalates to HUMAN_REQUIRED.
    third_qa = await run_qa(force=True)
    assert third_qa["status"] == "FAIL"
    attempt3 = await run_repair()
    assert attempt3["attempt"] == 3
    assert attempt3["rung"] == "HUMAN_REQUIRED"
    assert attempt3["applied"] is False
    assert attempt3["status"] == "REPAIRING"

    plans = (await db_session.execute(
        select(RepairPlan).where(RepairPlan.shot_id == shot.id).order_by(RepairPlan.attempt)
    )).scalars().all()
    assert [p.rung for p in plans] == ["MICRO", "MACRO", "HUMAN_REQUIRED"]

    # Every QA + repair dispatch through this chain is in the audit trail.
    qa_audits = (await db_session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project.id, AuditRecord.tool_name == "run_qa_committee")
    )).scalars().all()
    assert len(qa_audits) == 3 and all(a.error is None for a in qa_audits)


# -- the stubbed final gate ---------------------------------------------


@pytest.mark.asyncio
async def test_approve_requires_a_passing_qa_result(db_session, clean_db, captured_events, tmp_path):
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    approval = ApprovalService(db_session)

    with pytest.raises(ApprovalServiceError, match="no passing QA result"):
        await approval.approve(shot.id)

    qa = QACommitteeService(db_session, registry=registry)
    passed = await qa.run(shot.id)
    assert passed["status"] == "PASS"

    result = await approval.approve(shot.id)
    assert result["status"] == "APPROVED"

    row = await ShotRepository(db_session).get(shot.id)
    assert row.status == "APPROVED"


@pytest.mark.asyncio
async def test_approve_is_rejected_once_already_approved(db_session, clean_db, captured_events, tmp_path):
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    qa = QACommitteeService(db_session, registry=registry)
    await qa.run(shot.id)

    approval = ApprovalService(db_session)
    await approval.approve(shot.id)

    with pytest.raises(ApprovalServiceError, match="already approved"):
        await approval.approve(shot.id)


@pytest.mark.asyncio
async def test_approve_rejects_a_forced_fail_even_after_repair_is_requested(
    db_session, clean_db, captured_events, tmp_path
):
    """A shot mid-repair (REPAIRING, or QA_PENDING awaiting a fresh
    committee pass) still has a FAIL as its latest QA result, so the
    gate correctly refuses it - approval only ever follows a genuine
    PASS, first-try or post-repair, never a status the human hasn't
    actually seen pass QA."""
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    qa_service = QACommitteeService(db_session, registry=registry)
    await qa_service.run(shot.id, force_fail=True)

    with pytest.raises(ApprovalServiceError, match="no passing QA result"):
        await ApprovalService(db_session).approve(shot.id)

    # Repair it, then a genuine (unforced) pass makes it approvable.
    repair = RepairService(db_session, video=VideoGenerationService(db_session, registry=registry))
    await repair.repair(shot.id)
    resolved = await qa_service.run(shot.id)
    assert resolved["status"] == "PASS"

    result = await ApprovalService(db_session).approve(shot.id)
    assert result["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_only_the_directors_approval_scope_may_approve(db_session, clean_db, captured_events, tmp_path):
    project, shot, registry = await _generated_shot(db_session, tmp_path)
    qa = QACommitteeService(db_session, registry=registry)
    await qa.run(shot.id)
    approval = ApprovalService(db_session)

    with pytest.raises(ToolPermissionDeniedError):  # the QA agent may not sign off shots itself
        await dispatch_and_audit(
            db_session, project_id=project.id, role=AgentRole.QA_AGENT, tool_name="approve_shot",
            tool_input={"shot_id": shot.id}, executor=approval.tool_approve_shot, agent_decision="x",
        )

    approved = await dispatch_and_audit(
        db_session, project_id=project.id, role=AgentRole.DIRECTOR, tool_name="approve_shot",
        tool_input={"shot_id": shot.id}, executor=approval.tool_approve_shot, agent_decision="x",
    )
    assert approved.result["status"] == "APPROVED"

    # The Gateway audits every dispatch, denied or not (Day 9): the
    # QA_AGENT's denied attempt above and this DIRECTOR success are both
    # in the trail, one with an error recorded and one without.
    audits = (await db_session.execute(
        select(AuditRecord).where(AuditRecord.project_id == project.id, AuditRecord.tool_name == "approve_shot")
    )).scalars().all()
    assert len(audits) == 2
    by_error = sorted((a.error is None) for a in audits)
    assert by_error == [False, True]
