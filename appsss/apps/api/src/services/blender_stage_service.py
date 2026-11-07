"""
Blender stage (Week 3 Day 12, Engineer 1) - physics before pixels.

run_proxy(shot_id) turns a PLANNED ShotSpec version into a physics proxy
and registers everything in the Asset Registry with lineage:

    physics_proxy (JSON: scene layout + per-pass hashes)   <- root
      |- blender_depth   (PNG)   parent_asset = physics_proxy
      |- blender_normal  (PNG)   parent_asset = physics_proxy
      |- blender_canny   (PNG)   parent_asset = physics_proxy
      |- blender_mask    (PNG)   parent_asset = physics_proxy

Every asset's content_hash is the sha256 of its bytes (AssetRegistry is
content-addressed), and metadata carries renderer (MOCK unless a real
Blender service is configured), pass, width/height, project/shot/
shotspec ids and version. The version row gets physics_proxy_asset_id
and status BLENDER_READY - which is exactly what the Gateway's physics
gate (services/physics_gate.py) checks before any pixel tool may run.

Idempotent: a version that already has a proxy is returned as-is.
"""

import hashlib
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.event import EventType
from packages.contracts.shotspec import ShotSpecStatus
from src.core.assets.registry import AssetRegistry
from src.core.blender.client import PASS_NAMES, BlenderClient, BlenderRequest, get_blender_client
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.errors import APIException
from src.repositories.project_repository import ProjectRepository
from src.repositories.shot_repository import ShotRepository

PHYSICS_AGENT_ID = str(uuid5(NAMESPACE_URL, "avos:agent:physics"))

PROXY_ASSET_TYPE = "physics_proxy"


def pass_asset_type(name: str) -> str:
    return f"blender_{name}"


class BlenderStageError(RuntimeError):
    """The shot is not in a state the Blender stage can run on."""


class BlenderStageService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        client: BlenderClient | None = None,
        registry: AssetRegistry | None = None,
    ) -> None:
        self.session = session
        self.client = client or get_blender_client()
        self.registry = registry or AssetRegistry(session)
        self.shots = ShotRepository(session)
        self.projects = ProjectRepository(session)

    async def run_proxy(self, shot_id: str, *, version: int | None = None) -> dict[str, Any]:
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise APIException(code="not_found", message="Shot not found.", status_code=404)
        row = await self.shots.get_version(shot.id, version or shot.current_version)
        if row is None:
            raise APIException(code="not_found", message="Shot version not found.", status_code=404)

        if row.physics_proxy_asset_id is not None:
            return self._summary(shot, row, rendered=False, renderer=None, passes={})

        if row.status != ShotSpecStatus.PLANNED.value:
            raise BlenderStageError(
                f"Shot {shot.shot_index + 1} v{row.version} is {row.status}; the Blender stage "
                "needs a continuity-validated (PLANNED) ShotSpec."
            )

        project = await self.projects.get(shot.project_id)
        result = await self.client.render_proxy(
            BlenderRequest(
                project_id=shot.project_id,
                shot_id=shot.id,
                shotspec_id=row.id,
                version=row.version,
                content_hash=row.content_hash,
                aspect_ratio=project.aspect_ratio if project else "9:16",
                content=row.content,
            )
        )

        common = {
            "renderer": result.renderer,
            "mock": result.is_mock,
            "project_id": shot.project_id,
            "shot_id": shot.id,
            "shot_index": shot.shot_index,
            "shotspec_id": row.id,
            "shotspec_version": row.version,
            "shotspec_content_hash": row.content_hash,
            "width": result.width,
            "height": result.height,
        }

        proxy_doc = {
            **common,
            "scene": result.scene,
            "passes": {name: hashlib.sha256(data).hexdigest() for name, data in result.passes.items()},
        }
        proxy = await self.registry.store(
            project_id=shot.project_id,
            asset_type=PROXY_ASSET_TYPE,
            content=json.dumps(proxy_doc, sort_keys=True).encode("utf-8"),
            ext="json",
            created_by=PHYSICS_AGENT_ID,
            version=row.version,
            metadata=common,
            source="blender_mock" if result.is_mock else "blender",
        )
        proxy_id = proxy.asset.asset_id

        pass_ids: dict[str, str] = {}
        for name in PASS_NAMES:
            stored = await self.registry.store(
                project_id=shot.project_id,
                asset_type=pass_asset_type(name),
                content=result.passes[name],
                ext="png",
                created_by=PHYSICS_AGENT_ID,
                version=row.version,
                metadata={**common, "pass": name},
                parent_asset=proxy_id,
                source="blender_mock" if result.is_mock else "blender",
            )
            pass_ids[name] = str(stored.asset.asset_id)

        row.physics_proxy_asset_id = proxy_id
        await self.shots.set_version_status(shot, row, ShotSpecStatus.BLENDER_READY.value)

        queue_event(
            self.session,
            make_event(
                event_type=EventType.BLENDER_RENDERED,
                project_id=shot.project_id,
                payload={
                    "shot_id": shot.id,
                    "version": row.version,
                    "physics_proxy_asset_id": str(proxy_id),
                    "renderer": result.renderer,
                    "passes": pass_ids,
                },
            ),
        )
        return self._summary(shot, row, rendered=True, renderer=result.renderer, passes=pass_ids)

    @staticmethod
    def _summary(shot, row, *, rendered: bool, renderer: str | None, passes: dict[str, str]) -> dict[str, Any]:
        return {
            "shot_id": shot.id,
            "shot_index": shot.shot_index,
            "version": row.version,
            "status": row.status,
            "physics_proxy_asset_id": str(row.physics_proxy_asset_id),
            "rendered": rendered,
            "renderer": renderer,
            "passes": passes,
        }

    # -- Gateway executor (Physics agent) ----------------------------------------

    async def tool_run_blender_proxy(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = await self.run_proxy(arguments["shot_id"], version=arguments.get("version"))
        return {**summary, "model": f"blender:{summary['renderer'] or 'cached'}"}
