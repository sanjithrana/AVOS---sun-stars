import hashlib
import json
import time
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.tool_gateway.default_registry import create_default_registry
from agentic_core.tool_gateway.gateway import ToolExecutor, ToolResult, dispatch
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.event import EventType
from src.config.settings import settings
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.repositories.audit_repository import AuditRepository
from src.repositories.project_repository import ProjectRepository
from src.services.physics_gate import constitution_check_for

BUDGET_WARNING_RATIO = Decimal("0.8")


def _hash(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def trace_entry(record) -> dict[str, Any]:
    """Single wire shape for a decision-trace row, shared by
    GET /agents/trace and the AGENT_ACTION_RECORDED SSE event so the
    frontend can append live entries without re-fetching."""
    return {
        "id": str(record.id),
        "agent_decision": record.agent_decision,
        "tool_name": record.tool_name,
        "status": "error" if record.error else "success",
        "duration_ms": record.duration_ms,
        "cost": float(record.cost),
        "model": record.model,
        "error": record.error,
        "created_at": record.created_at.isoformat(),
    }


async def dispatch_and_audit(
    session: AsyncSession,
    *,
    project_id: str,
    role: AgentRole,
    tool_name: str,
    tool_input: dict[str, Any],
    executor: ToolExecutor,
    agent_decision: str,
    correlation_id: str | None = None,
) -> ToolResult:
    """
    Dispatch a tool call through the Tool Gateway, then record:
      - exactly one audit_records row (success or failure)   [Day 9]
      - a budget_spent increment on the project               [Day 10]
      - BUDGET_WARNING (>=80%) / BUDGET_EXCEEDED (>=100%) events
      - an AGENT_ACTION_RECORDED event for the live Agent Chat

    Every agent tool call in the api/worker goes through here instead of
    calling gateway.dispatch() directly, so the audit trail is complete
    by construction. Events are *queued* on the session and published
    only after the caller commits (see core/events/outbox.py).
    """
    registry = create_default_registry()
    audit_repo = AuditRepository(session)
    project_repo = ProjectRepository(session)
    cost = settings.placeholder_cost_per_tool_call

    started = time.monotonic()
    error: str | None = None
    result_payload: dict[str, Any] = {}

    try:
        result = await dispatch(
            registry=registry,
            role=role,
            tool_name=tool_name,
            tool_input=tool_input,
            executor=executor,
            constitution_check=constitution_check_for(session),
        )
        result_payload = result.result if isinstance(result.result, dict) else {}
        # A tool that spent real money (e.g. a paid video clip) reports
        # it; that's added on top of the flat per-call placeholder.
        extra_cost = result_payload.get("cost_usd")
        if isinstance(extra_cost, (int, float)) and extra_cost > 0:
            cost = round(float(cost) + float(extra_cost), 4)
        return result
    except Exception as exc:  # noqa: BLE001 - re-raised after auditing
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)

        record = await audit_repo.create(
            project_id=project_id,
            agent_decision=agent_decision,
            tool_name=tool_name,
            tool_call_input=tool_input,
            tool_result=result_payload,
            duration_ms=duration_ms,
            cost=cost,
            model=str(result_payload.get("model", "n/a")),
            input_hash=_hash(tool_input),
            output_hash=_hash(result_payload),
            error=error,
        )

        queue_event(
            session,
            make_event(
                event_type=EventType.AGENT_ACTION_RECORDED,
                project_id=project_id,
                correlation_id=correlation_id or str(record.id),
                payload=trace_entry(record),
            ),
        )

        project = await project_repo.add_budget_spent(project_id, cost)

        if project is not None and project.budget_limit:
            # Exact decimal math (NUMERIC columns): in floats 0.02/0.025
            # is 0.7999999..., so the 80% warning never fired at 80%.
            spent = Decimal(str(project.budget_spent))
            limit = Decimal(str(project.budget_limit))
            if spent >= limit * BUDGET_WARNING_RATIO:
                queue_event(
                    session,
                    make_event(
                        event_type=(
                            EventType.BUDGET_EXCEEDED
                            if spent >= limit
                            else EventType.BUDGET_WARNING
                        ),
                        project_id=project_id,
                        correlation_id=correlation_id or str(record.id),
                        payload={"budget_spent": float(spent), "budget_limit": float(limit)},
                    ),
                )
