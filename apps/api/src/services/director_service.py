from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.director.context_manager import ProjectSummary, build_project_summary
from agentic_core.director.director import (
    DirectorAction,
    DirectorDecision,
    PipelineState,
    StudioDirector,
)
from agentic_core.models.llm.factory import get_llm_provider
from agentic_core.pipelines.script.validator import has_blocking_errors, validate_script
from agentic_core.tool_gateway.permissions import AgentRole
from agentic_core.styles import get_style
from agentic_core.tool_gateway.tools.generate_script import GenerateScriptTool
from agentic_core.tool_gateway.tools.research_topic import ResearchTopicTool
from agentic_core.tool_gateway.tools.search_memory import SearchMemoryTool
from packages.contracts.event import EventType
from packages.contracts.human_gate import HumanGateType
from packages.contracts.script import Script
from src.core.events.factory import make_event
from src.core.events.outbox import commit_and_publish, queue_event
from src.database.models.human_gate import HumanGate
from src.database.models.project import Project
from src.domain.jobs.models import JobStatus
from src.domain.projects.status import ProjectStatus
from src.repositories.human_gate_repository import HumanGateRepository
from src.repositories.job_repository import JobRepository
from src.repositories.project_repository import ProjectRepository
from src.services.gateway_bridge import dispatch_and_audit
from src.services.project_service import ProjectNotFoundError


class DirectorStoppedError(RuntimeError):
    """The Director decided not to continue (e.g. budget exhausted)."""


class ScriptRejectedByValidatorError(RuntimeError):
    """The generated script failed blocking validation checks."""


class DirectorService:
    """
    Week 2 Director orchestration (api side of the Eng1/Eng2 boundary).

    Each public method is one durable step, called by a thin Temporal
    activity (src/temporal/activities/*). Every step:
      1. assembles a ProjectSummary from real DB rows (Context Manager),
      2. asks StudioDirector.decide() what to do and why,
      3. dispatches tools through dispatch_and_audit (audit + budget),
      4. updates project/job state and commits, then publishes events.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectRepository(session)
        self.gates = HumanGateRepository(session)
        self.jobs = JobRepository(session)
        self.director = StudioDirector()

    # -- Context Manager --------------------------------------------------

    async def _get_project(self, project_id: str) -> Project:
        project = await self.projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    async def build_summary(
        self,
        project_id: str,
        prior_memory: list[str] | None = None,
    ) -> ProjectSummary:
        project = await self._get_project(project_id)
        return build_project_summary(
            project_id=project.id,
            topic=project.topic,
            duration_seconds=project.duration_seconds,
            aspect_ratio=project.aspect_ratio,
            status=project.status,
            budget_limit=float(project.budget_limit) if project.budget_limit else None,
            budget_spent=float(project.budget_spent or 0),
            prior_memory=prior_memory or [],
        )

    def _decide(self, summary: ProjectSummary, state: PipelineState) -> DirectorDecision:
        decision = self.director.decide(summary, state)
        if decision.action == DirectorAction.STOP:
            raise DirectorStoppedError(decision.reason)
        return decision

    async def _set_project_status(self, project_id: str, status: ProjectStatus) -> None:
        await self.projects.set_status(project_id, status.value)
        queue_event(
            self.session,
            make_event(
                event_type=EventType.PROJECT_STATUS_CHANGED,
                project_id=project_id,
                payload={"status": status.value},
            ),
        )

    # -- Step 1: research ------------------------------------------------

    async def research(self, project_id: str, *, job_id: str | None = None) -> list[str]:
        project = await self._get_project(project_id)
        llm = get_llm_provider(project.llm_provider)

        if job_id:
            job = await self.jobs.update_status(UUID(job_id), JobStatus.RUNNING)
            if job is not None:
                queue_event(
                    self.session,
                    make_event(
                        event_type=EventType.JOB_STATUS_CHANGED,
                        project_id=project_id,
                        payload={"job_id": job_id, "status": job.status.value},
                    ),
                )
        await self._set_project_status(project_id, ProjectStatus.RESEARCHING)

        summary = await self.build_summary(project_id)

        # Memory lookup first (AVOS-04 s6), logged as its own trace entry.
        memory_result = await dispatch_and_audit(
            self.session,
            project_id=project_id,
            role=AgentRole.DIRECTOR,
            tool_name="search_memory",
            tool_input={"query": summary.topic},
            executor=SearchMemoryTool().execute,
            agent_decision=(
                f"Checking memory for prior work on '{summary.topic}' "
                "before researching."
            ),
        )
        summary = await self.build_summary(
            project_id, prior_memory=memory_result.result.get("results", [])
        )

        decision = self._decide(summary, PipelineState())

        research_result = await dispatch_and_audit(
            self.session,
            project_id=project_id,
            role=AgentRole.RESEARCH_AGENT,
            tool_name="research_topic",
            tool_input={"topic": summary.topic},
            executor=ResearchTopicTool(llm=llm).execute,
            agent_decision=decision.reason,
        )

        await commit_and_publish(self.session)
        return list(research_result.result["notes"])

    # -- Step 2: script + human gate ---------------------------------------

    async def write_script(
        self,
        project_id: str,
        *,
        research_notes: list[str],
        workflow_id: str | None = None,
    ) -> HumanGate:
        # Idempotency: if a retried activity already opened this
        # workflow's gate, return it instead of opening a duplicate.
        if workflow_id:
            existing = await self.gates.get_for_workflow(
                workflow_id, HumanGateType.SCRIPT_APPROVAL.value
            )
            if existing is not None:
                return existing

        project = await self._get_project(project_id)
        summary = await self.build_summary(project_id)
        decision = self._decide(summary, PipelineState(has_research=True))

        script_result = await dispatch_and_audit(
            self.session,
            project_id=project_id,
            role=AgentRole.NARRATIVE_AGENT,
            tool_name="generate_script",
            tool_input={
                "project_id": project_id,
                "topic": summary.topic,
                "duration_seconds": summary.duration_seconds,
                "aspect_ratio": summary.aspect_ratio,
                "research_notes": research_notes,
                "style_guidance": get_style(project.style_preset).script_guidance,
            },
            executor=GenerateScriptTool(llm=get_llm_provider(project.llm_provider)).execute,
            agent_decision=decision.reason,
        )

        script = Script.model_validate(script_result.result)
        issues = validate_script(script, target_duration_seconds=summary.duration_seconds)

        if has_blocking_errors(issues):
            await commit_and_publish(self.session)  # keep the audit row
            raise ScriptRejectedByValidatorError(
                "; ".join(i.message for i in issues if i.severity == "error")
            )

        payload = script.model_dump(mode="json")
        payload["validation_issues"] = [i.model_dump() for i in issues]

        gate = await self.gates.create(
            project_id=project_id,
            gate_type=HumanGateType.SCRIPT_APPROVAL.value,
            payload=payload,
            workflow_id=workflow_id,
        )

        await self._set_project_status(project_id, ProjectStatus.AWAITING_APPROVAL)
        queue_event(
            self.session,
            make_event(
                event_type=EventType.SCRIPT_GENERATED,
                project_id=project_id,
                payload={
                    "scene_count": len(script.scenes),
                    "estimated_seconds": script.total_estimated_seconds,
                },
            ),
        )
        queue_event(
            self.session,
            make_event(
                event_type=EventType.HUMAN_GATE_OPENED,
                project_id=project_id,
                payload={
                    "gate_id": str(gate.id),
                    "gate_type": gate.gate_type,
                    "message": "Script awaiting human approval.",
                },
            ),
        )

        await commit_and_publish(self.session)
        return gate
