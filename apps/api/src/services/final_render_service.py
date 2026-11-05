"""
Final render (Video agent, `assemble_video` through the audited Tool
Gateway): every shot's first candidate - its AI clip when the project's
video provider made one, else its still animated with a camera move -
in timeline order, with the narration and burned-in word-by-word
captions, rendered to one MP4 and stored as a `final_video` asset.
"""

import logging
import os
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.models.video.factory import resolve_video_choice
from agentic_core.pipelines.render.assemble import RenderSegment, pick_music, pick_sfx, render_video
from agentic_core.styles import get_style
from agentic_core.pipelines.render.captions import CaptionWord
from agentic_core.tool_gateway.permissions import AgentRole
from packages.contracts.event import EventType
from src.core.assets.registry import AssetRegistry
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.repositories.project_repository import ProjectRepository
from src.repositories.shot_repository import ShotRepository
from src.repositories.video_generation_repository import VideoGenerationRepository
from src.services.gateway_bridge import dispatch_and_audit
from src.services.video_generation_service import VIDEO_AGENT_ID

logger = logging.getLogger(__name__)

FINAL_ASSET_TYPE = "final_video"


class FinalRenderError(RuntimeError):
    """Nothing renderable yet (no shots / no narration)."""


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


def _captions_enabled() -> bool:
    return (os.getenv("CAPTIONS") or "on").strip().lower() not in ("0", "off", "false", "no")


class FinalRenderService:
    def __init__(self, session: AsyncSession, *, registry: AssetRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or AssetRegistry(session)
        self.projects = ProjectRepository(session)
        self.shots = ShotRepository(session)
        self.generations = VideoGenerationRepository(session)

    async def _asset_bytes(self, asset_id: str | None) -> bytes | None:
        if not asset_id:
            return None
        asset = await self.registry.get(UUID(str(asset_id)))
        if asset is None:
            return None
        try:
            return self.registry.read_bytes(asset)
        except OSError:
            logger.warning("Asset %s is registered but its file is missing.", asset_id)
            return None

    async def _segments(self, project_id: str) -> list[RenderSegment]:
        segments: list[RenderSegment] = []
        for shot in await self.shots.list_by_project(project_id):
            current = await self.shots.current_version(shot)
            if current is None:
                continue
            generation = await self.generations.get_latest_for_shot(shot.id, current.version)
            candidate = (generation.candidates[0] if generation and generation.candidates else {}) or {}
            prompt = ((generation.compiled_prompt or {}).get("prompt") or "") if generation else ""
            segments.append(
                RenderSegment(
                    start=float(shot.start_time or 0),
                    end=float(shot.end_time or 0),
                    clip=await self._asset_bytes(candidate.get("render_asset_id")),
                    image=await self._asset_bytes(candidate.get("thumbnail_asset_id")),
                    seed=candidate.get("seed"),
                    prompt=prompt or shot.beat_label,
                )
            )
        return segments

    async def render(self, project_id: str, audio: dict[str, Any]) -> dict[str, Any]:
        project = await self.projects.get(project_id)
        if project is None:
            raise FinalRenderError(f"Project {project_id} not found.")
        audio_asset_id = audio.get("asset_id")
        narration = await self._asset_bytes(audio_asset_id)
        if not narration:
            raise FinalRenderError("No narration audio to render with.")
        segments = await self._segments(project_id)
        if not segments:
            raise FinalRenderError("The project has no shots to render.")

        words = [
            CaptionWord(text=w["word"], start=float(w["start"]), end=float(w["end"]))
            for w in audio.get("words") or []
        ]
        style = get_style(project.style_preset)
        library = os.getenv("MUSIC_DIR") or "/app/music"
        music = pick_music(library, style.music_mood, project_id) if os.getenv("MUSIC", "on") != "off" else None
        sfx = pick_sfx(library) if os.getenv("SFX", "on") != "off" else None
        result = await render_video(
            segments,
            audio=narration,
            audio_ext=audio.get("format") or "wav",
            words=words,
            aspect_ratio=project.aspect_ratio or "9:16",
            size=os.getenv("RENDER_SIZE"),
            captions=_captions_enabled(),
            caption_font=os.getenv("CAPTION_FONT") or "DejaVu Sans",
            caption_words=style.caption_words,
            music=music,
            music_volume=_float_env("MUSIC_VOLUME", 0.22),
            sfx=sfx,
            sfx_volume=_float_env("SFX_VOLUME", 0.5),
        )

        video_choice = resolve_video_choice(project.video_provider) or "none"
        stored = await self.registry.store(
            project_id=project_id,
            asset_type=FINAL_ASSET_TYPE,
            content=result.video,
            ext="mp4",
            created_by=VIDEO_AGENT_ID,
            metadata={
                "duration_seconds": result.duration_seconds,
                "width": result.width,
                "height": result.height,
                "shot_sources": result.sources,
                "video_provider": video_choice,
                "image_provider": project.image_provider,
                "audio_asset_id": str(audio_asset_id),
                "captions": _captions_enabled(),
                "style_preset": style.name,
                "music": result.music,
                "sfx": sfx.name if sfx else None,
            },
            source=f"render:{video_choice}",
        )
        asset_id = str(stored.asset.asset_id)
        summary = {
            "asset_id": asset_id,
            "duration_seconds": result.duration_seconds,
            "width": result.width,
            "height": result.height,
            "shot_sources": result.sources,
            "video_provider": video_choice,
            "size_bytes": len(result.video),
            "style_preset": style.name,
            "music": result.music,
        }
        queue_event(
            self.session,
            make_event(event_type=EventType.VIDEO_ASSEMBLED, project_id=project_id, payload=summary),
        )
        logger.info(
            "Final video for project %s: %.1fs %dx%d, shots from %s.",
            project_id, result.duration_seconds, result.width, result.height, result.sources,
        )
        return summary

    async def render_through_gateway(self, project_id: str, audio: dict[str, Any]) -> dict[str, Any]:
        async def executor(arguments: dict[str, Any]) -> dict[str, Any]:
            summary = await self.render(arguments["project_id"], audio)
            return {**summary, "model": f"ffmpeg-render+{summary['video_provider']}"}

        clips = "AI clips" if resolve_video_choice((await self.projects.get(project_id)).video_provider) else "animated stills"
        result = await dispatch_and_audit(
            self.session,
            project_id=project_id,
            role=AgentRole.VIDEO_AGENT,
            tool_name="assemble_video",
            tool_input={"project_id": project_id, "audio_asset_id": str(audio.get("asset_id"))},
            executor=executor,
            agent_decision=(
                f"Director -> Video agent: assemble the final video from every shot's {clips}, "
                "the narration and word-by-word captions."
            ),
        )
        return dict(result.result)
