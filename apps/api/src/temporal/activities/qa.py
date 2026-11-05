"""QA → repair loop and the optional shot review (the diagram's "AVOS QA Agent → PASS / FAIL → Repair Agent → GPU").

qa_repair_activity, per shot, after its pictures and clip exist:
    QA committee ── PASS ─────────────────────────────▶ done
        └── FAIL → Repair agent (MICRO: new seeds · MACRO: corrected prompt) → GPU → QA again …
            … until the generation limit (max generations per shot) → NEEDS_REVIEW (a person decides; the last
            version is used meanwhile)

Every step goes through the audited tool gateway like the API routes, so the Studio's QA panel and the agent
trace show it. shots_review_gate_activity opens the optional "Review shots before rendering" gate.
"""
from dataclasses import dataclass
from typing import Any

from temporalio import activity

from agentic_core.tool_gateway.permissions import AgentRole
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, queue_event
from src.services.gateway_bridge import dispatch_and_audit
from src.services.qa_service import QACommitteeService, QAServiceError
from src.services.repair_service import RepairService, RepairServiceError
from src.temporal.activities._session import activity_session


@dataclass
class ShotQAInput:
    project_id: str
    shot_id: str


@dataclass
class QASettingsInput:
    project_id: str


@dataclass
class ShotsReviewInput:
    project_id: str
    workflow_id: str
    results: list[dict[str, Any]]


@activity.defn
async def qa_settings_activity(inp: QASettingsInput) -> dict[str, Any]:
    """The project's QA settings (generation limits): auto QA + repair on/off, review before rendering."""
    from agentic_core.model_fabric import policy
    from src.repositories.project_repository import ProjectRepository

    async with activity_session() as session:
        project = await ProjectRepository(session).get(inp.project_id)
        pol = policy.resolve(getattr(project, "generation_policy", None))
    return {"auto_qa": pol.auto_qa, "review_shots": pol.review_shots, "max_attempts": pol.max_attempts}


@activity.defn
async def qa_repair_activity(inp: ShotQAInput) -> dict[str, Any]:
    repairs = 0
    for _ in range(12):            # hard stop; the repair ladder escalates long before this
        async with activity_session() as session:
            shot = await QACommitteeService(session).shots.get(inp.shot_id)
            if shot is None:
                return {"shot_id": inp.shot_id, "status": "SKIPPED"}
            label = f"shot {shot.shot_index + 1}"
            try:
                qa = await dispatch_and_audit(
                    session, project_id=inp.project_id, role=AgentRole.QA_AGENT, tool_name="run_qa_committee",
                    tool_input={"shot_id": inp.shot_id, "candidate_index": 0, "force_fail": False},
                    executor=QACommitteeService(session).tool_run_qa_committee,
                    agent_decision=f"QA committee: automatic check of {label}" + (f" after repair {repairs}." if repairs else "."),
                )
            except QAServiceError as exc:
                await commit_and_publish(session)
                return {"shot_id": inp.shot_id, "shot_index": shot.shot_index, "status": "SKIPPED", "reason": str(exc)}
            await commit_and_publish(session)
        result = qa.result or {}
        if result.get("status") == "PASS":
            return {"shot_id": inp.shot_id, "shot_index": shot.shot_index, "status": "PASS", "repairs": repairs,
                    "score": result.get("score")}
        try:
            activity.heartbeat(f"{label}: QA failed, repairing")
        except RuntimeError:       # called outside a worker (tests)
            pass
        async with activity_session() as session:
            try:
                rep = await dispatch_and_audit(
                    session, project_id=inp.project_id, role=AgentRole.REPAIR_AGENT, tool_name="repair_shot",
                    tool_input={"shot_id": inp.shot_id}, executor=RepairService(session).tool_repair_shot,
                    agent_decision=f"Repair agent: automatic repair of {label} "
                                   f"(failed: {', '.join((result.get('evidence') or {}).get('failing_dimensions') or []) or 'QA'}).",
                )
            except RepairServiceError as exc:
                await commit_and_publish(session)
                return {"shot_id": inp.shot_id, "shot_index": shot.shot_index, "status": "NEEDS_REVIEW",
                        "repairs": repairs, "reason": str(exc)}
            await commit_and_publish(session)
        if (rep.result or {}).get("rung") == "HUMAN_REQUIRED":
            return {"shot_id": inp.shot_id, "shot_index": shot.shot_index, "status": "NEEDS_REVIEW",
                    "repairs": repairs, "score": result.get("score"),
                    "failing": (result.get("evidence") or {}).get("failing_dimensions") or []}
        repairs += 1
    return {"shot_id": inp.shot_id, "status": "NEEDS_REVIEW", "repairs": repairs}


@activity.defn
async def shots_review_gate_activity(inp: ShotsReviewInput) -> str:
    """Open the "review the shots before rendering" gate; the workflow waits for its decision."""
    from src.domain.projects.status import ProjectStatus
    from src.repositories.human_gate_repository import HumanGateRepository
    from src.services.director_service import DirectorService
    from packages.contracts.event import EventType

    async with activity_session() as session:
        passed = sum(1 for r in inp.results if r.get("status") == "PASS")
        gate = await HumanGateRepository(session).create(
            project_id=inp.project_id, gate_type="final_approval", workflow_id=inp.workflow_id,
            payload={"kind": "shots_review", "shots": inp.results, "passed": passed, "total": len(inp.results)},
        )
        await DirectorService(session)._set_project_status(inp.project_id, ProjectStatus.AWAITING_REVIEW)
        queue_event(session, make_event(
            event_type=EventType.HUMAN_GATE_OPENED, project_id=inp.project_id,
            payload={"gate_id": str(gate.id), "gate_type": gate.gate_type,
                     "message": f"Shots ready for review: {passed} of {len(inp.results)} passed QA."}))
        await commit_and_publish(session)
        return str(gate.id)
