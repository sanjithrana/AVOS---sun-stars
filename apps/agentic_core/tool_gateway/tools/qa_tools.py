"""
Gateway declarations for the Week 3 Day 14 QA/repair tools.

Same split as shotspec_tools.py: agentic_core owns *what* the tools are;
their executors live in the api layer (services/qa_service.py,
services/repair_service.py) because they read/write qa_results and
repair_plans - Engineer 1's tables.
"""

from pydantic import BaseModel, ConfigDict, Field

from tool_gateway.schemas import ToolSchema


class RunQACommitteeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    candidate_index: int = Field(default=0, ge=0)
    # Week 3 Day 15 (integration checkpoint): the mock Video generator and
    # the geometry dimension share the same SHOT_TYPE_SCALE mapping, so a
    # mock-generated candidate always earns a genuine PASS - there's no
    # naturally-occurring FAIL to drive the repair ladder with in a live
    # demo. force_fail lets a human deliberately fail a real evaluation
    # (both real dimensions still run; the verdict is overridden
    # afterward, loudly - forced=True on the response, a dedicated
    # geometry_mismatch-style issue, and its own audit trail) so the
    # ladder can be proven end to end through the real Gateway/SSE/UI,
    # not by seeding qa_results directly. Never used unless a human
    # explicitly asks for it.
    force_fail: bool = False


class RepairShotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str


class ApproveShotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str


RUN_QA_COMMITTEE = ToolSchema(
    name="run_qa_committee",
    description="Score a shot's generated candidate across the 6 QA dimensions (PASS/FAIL).",
    schema=RunQACommitteeInput.model_json_schema(),
    permission="qa",
    timeout=60,
)

REPAIR_SHOT = ToolSchema(
    name="repair_shot",
    description="Advance a failing shot's repair ladder one attempt (MICRO -> MACRO -> HUMAN_REQUIRED).",
    schema=RepairShotInput.model_json_schema(),
    permission="repair",
    timeout=120,
)

# Week 3 Day 15: the stubbed final gate (AVOS-18 s6.3's last step). Final
# Assembly/FFmpeg doesn't exist yet (Week 4+ ticket), so "approve" is the
# whole final stage for now - a human sign-off that a PASSED shot is done,
# recorded the same audited way as every other decision in the pipeline.
APPROVE_SHOT = ToolSchema(
    name="approve_shot",
    description="Final gate: a human approves a QA-passed shot (stubbed ahead of Final Assembly).",
    schema=ApproveShotInput.model_json_schema(),
    permission="approval",
    timeout=15,
)
