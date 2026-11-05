"""
Physics-before-pixels, enforced at the Tool Gateway (Week 3 Day 12).

AVOS-03 v1.1 s9.3: no pixels are generated for a shot until the Blender
stage has produced a physics proxy for *that shot's current ShotSpec
version*. The stateless half of the rule (a physics_proxy_asset_id must
be supplied) lives in agentic_core's check_constitution; this module adds
the database half and is what dispatch_and_audit passes to the Gateway:

    - the shot must exist
    - its current version must have completed the Blender stage
      (physics_proxy_asset_id set, status BLENDER_READY or later)
    - the supplied physics_proxy_asset_id must be exactly that proxy -
      a forged id, another shot's proxy, or the proxy of an older version
      (the ShotSpec was edited after rendering) is rejected

Every rejection is MissingDependencyError (code MISSING_DEPENDENCY), is
raised before the executor runs, and is audited by dispatch_and_audit.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.tool_gateway.constitution import (
    PHYSICS_GATED_TOOLS,
    MissingDependencyError,
    check_constitution,
)
from packages.contracts.shotspec import ShotSpecStatus
from src.repositories.shot_repository import ShotRepository

# Statuses a version can only reach after its Blender stage completed.
#
# FAILED belongs here too (Week 3 Day 15 fix): the QA committee moves a
# version to FAILED on a real FAIL (src/services/qa_service.py), and the
# repair ladder's MICRO/MACRO rungs then call generate_video_shot again
# for that exact version (src/services/repair_service.py) - regenerating
# against the *same* physics proxy is the whole point of a repair. Day
# 13/14's tests never caught this because they seeded a failing
# qa_results row directly, which never advances shot.status past
# QA_PENDING; only once Day 15 drove a real QA FAIL through the live
# endpoint (test_day15_integration.py) did FAILED's absence here surface,
# as a 409 MISSING_DEPENDENCY on every repair attempt.
POST_BLENDER_STATUSES = frozenset(
    s.value
    for s in (
        ShotSpecStatus.BLENDER_READY,
        ShotSpecStatus.GENERATING,
        ShotSpecStatus.QA_PENDING,
        ShotSpecStatus.PASSED,
        ShotSpecStatus.FAILED,
        ShotSpecStatus.REPAIRING,
        ShotSpecStatus.APPROVED,
    )
)


async def check_physics_dependency(session: AsyncSession, tool_name: str, tool_input: dict[str, Any]) -> None:
    def missing(message: str) -> MissingDependencyError:
        return MissingDependencyError(message, tool_name=tool_name, dependency="run_blender_proxy")

    shot_id = tool_input.get("shot_id")
    shots = ShotRepository(session)
    shot = await shots.get(shot_id) if shot_id else None
    if shot is None:
        raise missing(f"'{tool_name}' names unknown shot '{shot_id}'; nothing to ground it on.")

    current = await shots.current_version(shot)
    if current is None or current.physics_proxy_asset_id is None or current.status not in POST_BLENDER_STATUSES:
        raise missing(
            f"'{tool_name}' called for shot {shot.shot_index + 1} (v{shot.current_version}) "
            "before the Blender stage completed for it. Run run_blender_proxy first."
        )

    supplied = str(tool_input.get("physics_proxy_asset_id"))
    if supplied != str(current.physics_proxy_asset_id):
        raise missing(
            f"physics_proxy_asset_id {supplied} is not the physics proxy of shot "
            f"{shot.shot_index + 1} v{current.version} ({current.physics_proxy_asset_id}); "
            "it is forged, belongs to another shot, or is stale from an earlier version."
        )


def constitution_check_for(session: AsyncSession) -> Callable[[str, dict[str, Any]], Awaitable[None]]:
    """The Gateway constitution hook used by every api/worker dispatch."""

    async def _check(tool_name: str, tool_input: dict[str, Any]) -> None:
        check_constitution(tool_name, tool_input)
        if tool_name in PHYSICS_GATED_TOOLS:
            await check_physics_dependency(session, tool_name, tool_input)

    return _check
