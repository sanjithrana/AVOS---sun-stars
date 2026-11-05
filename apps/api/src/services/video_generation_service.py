"""
Video generation, idempotently (Week 3 Day 13, Engineer 1 -
AVOS-03 v1.1 s9.5, s10).

generate_video_shot is a physics-gated Gateway tool (constitution.py /
physics_gate.py, Day 12): the Gateway will not even call this service's
executor until a physics proxy exists for the shot's *current* ShotSpec
version. This module is what runs once that's true.

Idempotency (s9.5): every call carries (or is given a default) an
idempotency_key. A second call with the same key returns the first
call's video_generations row - same candidates, same asset ids, no new
Asset Registry writes and no new database row - rather than generating
again. The default key is derived from (shot_id, version, content_hash,
physics_proxy_asset_id), so an accidental double-submit (a UI double
click, a Temporal activity retry) is deduplicated even without the
caller supplying its own key.

Generation is mocked by default (deterministic PNG placeholders - see
_thumbnail_bytes), the same way it always was. Week 3 Day 16 added a
real path behind it: a project's saved image_provider/video_provider
(packages/contracts/project.py, set at project-creation time or via
IMAGE_PROVIDER/VIDEO_PROVIDER env vars) routes through
agentic_core.models.image/video.factory to an actual generator -
pollinations.ai (free, no key) or a self-hosted Automatic1111/ComfyUI
server for images, self-hosted only for video (see those factories'
docstrings for why). Whichever ran, the candidate/thumbnail assets are
tagged renderer=<provider name> instead of "MOCK" so it's always
visible in the Asset Registry which one produced a given asset.

Prompt Compiler compiles CANDIDATE_COUNT candidates, each registered as
a small JSON descriptor + a thumbnail (real, if an image provider is
configured, else the deterministic mock PNG) via the content-addressed
Asset Registry, with lineage exactly like the Blender proxy/passes
(root "video_generation" asset <- N "video_candidate" assets, each <- one
"video_thumbnail", optionally <- one "video_render" if a video provider
also ran for that candidate).
"""

import asyncio
import hashlib
import json
import logging
import os
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_core.models.image.base import ImageProvider
from agentic_core.models.image.factory import get_image_provider
from agentic_core.models.video.base import VideoProvider
from agentic_core.media.ffmpeg import run_ffmpeg, sniff_video_ext
from agentic_core.models.video.factory import (
    get_video_provider,
    is_image_to_video,
    resolve_video_choice,
)
from agentic_core.pipelines.shot.motion import facts_motion
from agentic_core.pipelines.shot.prompt_compiler import compile_prompt
from agentic_core.styles import get_style
from packages.contracts.event import EventType
from packages.contracts.shotspec import ShotContent, ShotSpecStatus
from src.core.assets.registry import AssetRegistry
from src.database.models.asset import Asset
from src.core.blender.png import encode_png
from src.core.events.factory import make_event
from src.core.events.outbox import queue_event
from src.errors import APIException
from src.repositories.project_repository import ProjectRepository
from src.repositories.shot_repository import ShotRepository
from src.repositories.video_generation_repository import VideoGenerationRepository

logger = logging.getLogger(__name__)

VIDEO_AGENT_ID = str(uuid5(NAMESPACE_URL, "avos:agent:video"))

_PRESENTER_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_PRESENTER_MADE: dict[tuple[int, str], bytes] = {}
IMAGE_CONCURRENCY = max(1, int(os.getenv("IMAGE_CANDIDATE_CONCURRENCY") or 3))   # pictures of one shot at once
CANDIDATE_COUNT = 3  # AVOS-08 s8.3: 3 candidates per shot for QA/human pick
CANDIDATE_ASSET_TYPE = "video_candidate"
THUMB_ASSET_TYPE = "video_thumbnail"
RENDER_ASSET_TYPE = "video_render"
ROOT_ASSET_TYPE = "video_generation"
THUMB_WIDTH, THUMB_HEIGHT = 64, 36

# Real-generator resolution per aspect ratio (mock thumbnails stay at
# THUMB_WIDTH/THUMB_HEIGHT regardless - this only applies when an image
# or video provider is actually configured). Matches the final render's
# 720p frame so animated stills stay sharp.
RESOLUTIONS_BY_ASPECT = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1024, 1024)}

# Only the first candidate of each shot gets a video clip: clips are the
# slow/expensive part (a paid API bills per clip, a local GPU takes
# minutes), and the final render uses candidate 0. The other candidates
# keep their stills for QA / a human pick.
RENDERED_CANDIDATES = 1
PRESENTER_ASSET_TYPE = "presenter"

# Statuses a version can be generated from without downgrading further
# progress if it's regenerated later with a fresh idempotency key.
GENERATABLE_STATUSES = frozenset({ShotSpecStatus.BLENDER_READY.value, ShotSpecStatus.GENERATING.value})


class VideoGenerationError(RuntimeError):
    """The shot/version is not in a state generation can run against."""


def default_idempotency_key(shot_id: str, version: int, content_hash: str, physics_proxy_asset_id: str) -> str:
    return hashlib.sha256(
        f"{shot_id}:{version}:{content_hash}:{physics_proxy_asset_id}".encode("utf-8")
    ).hexdigest()


def _thumbnail_bytes(params_hash: str, candidate_index: int) -> bytes:
    """Deterministic placeholder frame (a solid color seeded from the
    compiled prompt's hash): a real, valid PNG, distinct per candidate
    and per shot, standing in for a rendered video frame."""
    seed = int(hashlib.sha256(f"{params_hash}:{candidate_index}".encode()).hexdigest()[:6], 16)
    r, g, b = (seed >> 16) & 0xFF, (seed >> 8) & 0xFF, seed & 0xFF
    row = bytes((r, g, b)) * THUMB_WIDTH
    rows = [row for _ in range(THUMB_HEIGHT)]
    return encode_png(
        THUMB_WIDTH, THUMB_HEIGHT, rows, channels=3,
        text={"avos:renderer": "MOCK", "avos:params_hash": params_hash, "avos:candidate": str(candidate_index)},
    )


async def _generate_thumbnail(
    image_provider: ImageProvider | None,
    *,
    prompt: str,
    params_hash: str,
    candidate_index: int,
    seed: int,
    aspect_ratio: str,
) -> bytes:
    """Real thumbnail via image_provider if one is configured, else the
    unchanged deterministic mock PNG. Raises on provider failure rather
    than silently falling back to the mock - a person who picked a real
    provider should see it error, not get a placeholder that looks
    identical to what mock mode always produced."""
    if image_provider is None:
        return _thumbnail_bytes(params_hash, candidate_index)

    width, height = RESOLUTIONS_BY_ASPECT.get(aspect_ratio, (512, 512))
    return await image_provider.generate(prompt, width=width, height=height, seed=seed)


def _sniff_image_ext(data: bytes) -> str:
    """A real provider's response format isn't guaranteed (Pollinations
    can return JPEG or PNG depending on model/request), so this reads
    the magic bytes rather than assuming - a wrong extension on a
    content-addressed asset would make it unopenable as an image."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "png"  # unknown - keep the previous default rather than guess wrong


async def _generate_render(
    video_provider: VideoProvider | None,
    *,
    prompt: str,
    seed: int,
    aspect_ratio: str,
    duration_seconds: float = 4.0,
    image: bytes | None = None,
    audio: bytes | None = None,
) -> bytes | None:
    """None when no video provider is configured - the caller skips
    storing a video_render asset (the final render then animates the
    shot's still itself). ``image`` is the shot's still, for
    image-to-video providers (the presenter portrait for avatar models);
    ``audio`` is this shot's narration, only for models that use it."""
    if video_provider is None:
        return None

    width, height = RESOLUTIONS_BY_ASPECT.get(aspect_ratio, (512, 512))
    extra = {"audio": audio} if getattr(video_provider, "wants_audio", None) else {}
    return await video_provider.generate(
        prompt, width=width, height=height, seed=seed,
        duration_seconds=duration_seconds, image=image, **extra,
    )


PRESENTER_PROMPT = (
    "Head-and-shoulders portrait of a friendly presenter looking straight at the camera, mouth closed, "
    "neutral expression, even soft lighting, plain softly blurred background, centered, sharp face, {style}"
)


async def cut_audio(data: bytes, start: float, seconds: float) -> bytes:
    """[start, start+seconds) of an audio file as 16 kHz mono WAV (what the avatar models expect)."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "in.audio", Path(tmp) / "out.wav"
        src.write_bytes(data)
        await run_ffmpeg(["-y", "-ss", f"{max(0.0, start):.3f}", "-t", f"{max(0.5, seconds):.3f}", "-i", str(src),
                          "-ac", "1", "-ar", "16000", "-af", "apad", "-t", f"{max(0.5, seconds):.3f}", str(out)],
                         timeout=120)
        return out.read_bytes()


def image_provider_for(project) -> ImageProvider | None:
    """The project's image provider. Video providers that animate the
    shot's still need a real image, so when one of those was picked
    without an image provider, the free chain is used (Cloudflare Workers
    AI if configured, then Pollinations, then IMAGE_SERVICE_URL) rather
    than animating a 64x36 placeholder."""
    chosen = project.image_provider if project else None
    if not chosen and project is not None:
        if is_image_to_video(resolve_video_choice(project.video_provider)):
            chosen = "free"
    return get_image_provider(chosen)


class VideoGenerationService:
    def __init__(self, session: AsyncSession, *, registry: AssetRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or AssetRegistry(session)
        self.shots = ShotRepository(session)
        self.projects = ProjectRepository(session)
        self.generations = VideoGenerationRepository(session)

    async def generate(self, shot_id: str, **kwargs: Any) -> dict[str, Any]:
        """Generate a shot's pictures + clip under the project's Model Fabric limits, reporting every run
        (gpu_jobs rows, GPU_JOB_* events). See _generate for the work itself."""
        from agentic_core.model_fabric import workers
        from src.services.fabric_service import shot_context

        await workers.statuses()   # fresh GPU worker status for the providers' readiness checks (cached a few s)
        shot = await self.shots.get(shot_id)
        project = await self.projects.get(shot.project_id) if shot is not None else None
        version = kwargs.get("version") or (shot.current_version if shot is not None else None)
        label = f"{(project.name if project else '')[:40]} · shot {shot.shot_index + 1}" if shot is not None else None
        with shot_context(project, str(shot.id) if shot is not None else None, version, label=label):
            return await self._generate(shot_id, **kwargs)

    async def _generate(
        self,
        shot_id: str,
        *,
        physics_proxy_asset_id: str,
        version: int | None = None,
        idempotency_key: str | None = None,
        prompt_override: str | None = None,
        prompt_suffix: str | None = None,
        seed_offset: int = 0,
        candidate_count: int = CANDIDATE_COUNT,
    ) -> dict[str, Any]:
        shot = await self.shots.get(shot_id)
        if shot is None:
            raise APIException(code="not_found", message="Shot not found.", status_code=404)
        row = await self.shots.get_version(shot.id, version or shot.current_version)
        if row is None:
            raise APIException(code="not_found", message="Shot version not found.", status_code=404)

        if str(row.physics_proxy_asset_id) != str(physics_proxy_asset_id):
            # Defense in depth: the Gateway's physics_gate check already
            # enforces this before this executor ever runs (Day 12), but
            # this service is also reachable directly (e.g. the API
            # route), so it re-checks rather than trusting the caller.
            raise VideoGenerationError(
                f"physics_proxy_asset_id {physics_proxy_asset_id} does not match shot "
                f"{shot.shot_index + 1} v{row.version}'s physics proxy ({row.physics_proxy_asset_id})."
            )

        key = idempotency_key or default_idempotency_key(
            shot.id, row.version, row.content_hash, physics_proxy_asset_id
        )

        existing = await self.generations.get_by_idempotency_key(key)
        if existing is not None:
            if existing.shot_id != shot.id or existing.version != row.version:
                raise VideoGenerationError(
                    f"idempotency_key {key} was already used for a different shot/version "
                    f"({existing.shot_id} v{existing.version}); choose a distinct key."
                )
            logger.info(
                "[MOCK] Video generation: idempotency_key %s already satisfied for shot %s v%s; "
                "returning the cached result instead of generating again.",
                key, shot.shot_index + 1, row.version,
            )
            return self._summary(shot, row, existing, cached=True)

        content = ShotContent.model_validate(row.content)
        prompt_override = prompt_override or (content.prompt or "").strip() or None   # written in the Studio
        seed_offset = seed_offset + content.take * 7919                               # "regenerate": new seeds
        project = await self.projects.get(shot.project_id)
        aspect_ratio = project.aspect_ratio if project else "9:16"
        image_provider = image_provider_for(project)
        video_provider = get_video_provider(
            project.video_provider if project else None,
            llm_provider=project.llm_provider if project else None,
            environment_hint=get_style(project.style_preset if project else None).blender_environment,
        )
        start, end = float(shot.start_time or 0), float(shot.end_time or 0)
        shot_duration = max(1.0, end - start) if end > start else 4.0
        style = get_style(project.style_preset if project else None)
        clips_made = 0
        narration: bytes | None = None
        if video_provider is not None and getattr(video_provider, "wants_audio", None):
            narration = await self._narration_segment(shot.project_id, start, shot_duration)
            if narration is None and video_provider.wants_audio == "required":
                raise VideoGenerationError(
                    f"Video model '{video_provider.name}' speaks the narration, but project {shot.project_id} "
                    "has no narration audio yet."
                )
        presenter: bytes | None = None
        if video_provider is not None and getattr(video_provider, "needs_presenter", False):
            presenter = await self._presenter(shot.project_id, project, image_provider, aspect_ratio)

        # The clip's motion is planned as data (scene graph + motion blueprint) and compiled for the video model the
        # router is most likely to use (the same creative core as Animations → Series and its Director).
        video_model = getattr(video_provider, "model_id", None) or ("ltx-2.3" if getattr(video_provider, "name", "") == "best" else
                                                                      getattr(video_provider, "name", None) or "ltx-2.3")
        motion_plan = facts_motion(content, style, model=video_model, seconds=shot_duration)
        candidates: list[dict[str, Any]] = []
        first_compiled: dict[str, Any] | None = None
        prepared: list[tuple[int, Any, dict[str, Any], dict[str, Any]]] = []
        for index in range(candidate_count):
            compiled = compile_prompt(
                content,
                physics_proxy_asset_id=physics_proxy_asset_id,
                aspect_ratio=aspect_ratio,
                candidate_index=index,
            )
            if seed_offset:
                # Repair (Day 14): a MICRO/MACRO fix nudges the seed by a
                # deterministic, attempt-specific offset rather than
                # generating byte-identical candidates all over again.
                compiled = compile_prompt(
                    content,
                    physics_proxy_asset_id=physics_proxy_asset_id,
                    aspect_ratio=aspect_ratio,
                    candidate_index=index,
                    seed=compiled.seed + seed_offset,
                )
            compiled_dict = compiled.model_dump(mode="json")
            compiled_dict["motion_prompt"] = motion_plan["prompt"]
            compiled_dict["motion_blueprint"] = motion_plan["blueprint"]
            if prompt_override:
                compiled_dict["prompt"] = prompt_override
            elif prompt_suffix:
                # Repair (Day 14, MACRO rung): a corrective instruction is
                # appended rather than replacing the compiled prompt, so
                # the shot's own description/camera/lighting are kept.
                compiled_dict["prompt"] = f"{compiled_dict['prompt']} {prompt_suffix}"
            if first_compiled is None:
                first_compiled = compiled_dict
            common_meta = {
                "renderer": image_provider.name if image_provider else "MOCK",
                "project_id": shot.project_id,
                "shot_id": shot.id,
                "shot_index": shot.shot_index,
                "shotspec_id": row.id,
                "shotspec_version": row.version,
                "candidate_index": index,
                "compiled_prompt": compiled_dict,
            }
            prepared.append((index, compiled, compiled_dict, common_meta))

        # Generate first, store after. The pictures run concurrently (the GPU Scheduler spreads them over your GPUs,
        # hosted APIs take them in parallel), and the clip starts the moment its picture is ready instead of after
        # all of them. Only the bytes are made here; the database writes below stay in order on this session.
        sem = asyncio.Semaphore(IMAGE_CONCURRENCY)

        async def picture(item) -> bytes:
            index, compiled, compiled_dict, _ = item
            async with sem:
                return await _generate_thumbnail(
                    image_provider, prompt=compiled_dict["prompt"], params_hash=compiled.params_hash,
                    candidate_index=index, seed=compiled.seed, aspect_ratio=aspect_ratio,
                )

        async def clip(i: int, picture_task: "asyncio.Task[bytes]") -> bytes | None:
            thumbnail_bytes = await picture_task
            _, compiled, compiled_dict, _ = prepared[i]
            if presenter is not None:
                render_prompt = f'A presenter talking to camera about: {compiled_dict["prompt"]}'
            elif prompt_override or prompt_suffix:
                # a person's own prompt (or a repair's correction) leads; the compiled motion follows
                render_prompt = f'{compiled_dict["prompt"]} {compiled_dict["motion_prompt"]}'
            else:
                render_prompt = compiled_dict["motion_prompt"]
            return await _generate_render(
                video_provider,
                prompt=render_prompt,
                seed=compiled.seed,
                aspect_ratio=aspect_ratio,
                duration_seconds=shot_duration,
                image=presenter if presenter is not None else (thumbnail_bytes if image_provider is not None else None),
                audio=narration,
            )

        try:
            async with asyncio.TaskGroup() as tg:
                picture_tasks = [tg.create_task(picture(item)) for item in prepared]
                clip_tasks = {i: tg.create_task(clip(i, picture_tasks[i]))
                              for i in range(min(RENDERED_CANDIDATES, len(prepared)))}
        except BaseExceptionGroup as group:   # the first real error, as the callers expect (not a group)
            first: BaseException = group
            while isinstance(first, BaseExceptionGroup):
                first = first.exceptions[0]
            raise first from None

        for (index, compiled, compiled_dict, common_meta), picture_task in zip(prepared, picture_tasks):
            thumbnail_bytes = picture_task.result()
            candidate_asset = await self.registry.store(
                project_id=shot.project_id,
                asset_type=CANDIDATE_ASSET_TYPE,
                content=json.dumps(compiled_dict, sort_keys=True).encode("utf-8"),
                ext="json",
                created_by=VIDEO_AGENT_ID,
                version=row.version,
                metadata=common_meta,
                source="video_mock",
            )
            thumbnail_asset = await self.registry.store(
                project_id=shot.project_id,
                asset_type=THUMB_ASSET_TYPE,
                content=thumbnail_bytes,
                ext=_sniff_image_ext(thumbnail_bytes),
                created_by=VIDEO_AGENT_ID,
                version=row.version,
                metadata=common_meta,
                parent_asset=candidate_asset.asset.asset_id,
                source=image_provider.name if image_provider else "video_mock",
            )
            render_asset_id: str | None = None
            render_bytes = clip_tasks[index].result() if index in clip_tasks else None
            if render_bytes is not None:
                clips_made += 1
                render_asset = await self.registry.store(
                    project_id=shot.project_id,
                    asset_type=RENDER_ASSET_TYPE,
                    content=render_bytes,
                    ext=sniff_video_ext(render_bytes),
                    created_by=VIDEO_AGENT_ID,
                    version=row.version,
                    metadata={**common_meta, "renderer": video_provider.name if video_provider else "MOCK"},
                    parent_asset=candidate_asset.asset.asset_id,
                    source=video_provider.name if video_provider else "video_mock",
                )
                render_asset_id = str(render_asset.asset.asset_id)
            candidates.append({
                "index": index,
                "asset_id": str(candidate_asset.asset.asset_id),
                "thumbnail_asset_id": str(thumbnail_asset.asset.asset_id),
                "render_asset_id": render_asset_id,
                "seed": compiled.seed,
                "params_hash": compiled.params_hash,
            })

        root_doc = {
            "idempotency_key": key,
            "shot_id": shot.id,
            "shotspec_id": row.id,
            "shotspec_version": row.version,
            "candidates": candidates,
        }
        root_asset = await self.registry.store(
            project_id=shot.project_id,
            asset_type=ROOT_ASSET_TYPE,
            content=json.dumps(root_doc, sort_keys=True).encode("utf-8"),
            ext="json",
            created_by=VIDEO_AGENT_ID,
            version=row.version,
            metadata={"idempotency_key": key, "shot_id": shot.id, "candidate_count": len(candidates)},
            source="video_mock",
        )

        record = await self.generations.create(
            shot_id=shot.id,
            version=row.version,
            idempotency_key=key,
            compiled_prompt=first_compiled or {},
            candidates=candidates,
            asset_id=root_asset.asset.asset_id,
            created_by=VIDEO_AGENT_ID,
        )

        row.video_generation_asset_id = root_asset.asset.asset_id
        if row.status in GENERATABLE_STATUSES:
            await self.shots.set_version_status(shot, row, ShotSpecStatus.QA_PENDING.value)
        else:
            # Regenerated after already moving on (QA/repair) - keep the
            # existing status, just persist the new pointer/candidates.
            await self.session.flush()

        if image_provider is None:
            logger.warning(
                "[MOCK] Video generation: produced %d placeholder candidates for shot %s v%s. "
                "This is a deterministic mock, not a real render.",
                len(candidates), shot.shot_index + 1, row.version,
            )
        else:
            logger.info(
                "Video generation: produced %d candidates for shot %s v%s via image "
                "provider '%s'%s.",
                len(candidates), shot.shot_index + 1, row.version, image_provider.name,
                f" and video provider '{video_provider.name}'" if video_provider else "",
            )

        queue_event(
            self.session,
            make_event(
                event_type=EventType.VIDEO_GENERATED,
                project_id=shot.project_id,
                payload={
                    "shot_id": shot.id,
                    "version": row.version,
                    "video_generation_id": record.id,
                    "candidates": candidates,
                    "cached": False,
                },
            ),
        )

        summary = self._summary(shot, row, record, cached=False)
        if video_provider is not None and clips_made:
            summary["clip_cost_usd"] = round(video_provider.cost_per_clip_usd * clips_made, 4)
        return summary

    async def _latest_asset(self, project_id: str, asset_type: str) -> Asset | None:
        result = await self.session.execute(
            select(Asset)
            .where(
                Asset.asset_type == asset_type,
                or_(Asset.asset_metadata["project_id"].astext == project_id,
                    Asset.asset_metadata.contains({"project_ids": [project_id]})),
            )
            .order_by(Asset.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _narration_segment(self, project_id: str, start: float, seconds: float) -> bytes | None:
        """This shot's part of the project's narration (for audio-driven video and avatar models)."""
        asset = await self._latest_asset(project_id, "audio")
        if asset is None:
            return None
        return await cut_audio(self.registry.read_bytes(asset), start, seconds)

    async def _presenter(self, project_id: str, project, image_provider: ImageProvider | None,
                         aspect_ratio: str) -> bytes:
        """One presenter portrait per project (made once with the project's image model, then reused so the
        presenter looks the same in every shot)."""
        existing = await self._latest_asset(project_id, PRESENTER_ASSET_TYPE)
        if existing is not None:
            return self.registry.read_bytes(existing)
        # Shots run in parallel: the first one makes the portrait, the others wait for it instead of making it too.
        key = (id(asyncio.get_running_loop()), project_id)
        lock = _PRESENTER_LOCKS.setdefault(key, asyncio.Lock())
        async with lock:
            if key in _PRESENTER_MADE:
                data = _PRESENTER_MADE[key]
                await self.registry.store(project_id=project_id, asset_type=PRESENTER_ASSET_TYPE, content=data,
                                          ext=_sniff_image_ext(data), created_by=VIDEO_AGENT_ID, source="presenter")
                return data
            data = await self._make_presenter(project_id, project, image_provider, aspect_ratio)
            _PRESENTER_MADE[key] = data
            while len(_PRESENTER_MADE) > 16:          # only recent projects need it
                _PRESENTER_MADE.pop(next(iter(_PRESENTER_MADE)))
            return data

    async def _make_presenter(self, project_id: str, project, image_provider: ImageProvider | None,
                              aspect_ratio: str) -> bytes:
        provider = image_provider or get_image_provider("free")
        style = get_style(project.style_preset if project else None)
        prompt = os.getenv("AVATAR_PRESENTER_PROMPT") or PRESENTER_PROMPT.format(style=style.visual_style)
        width, height = RESOLUTIONS_BY_ASPECT.get(aspect_ratio, (720, 1280))
        seed = int(hashlib.sha256(project_id.encode()).hexdigest()[:8], 16)
        data = await provider.generate(prompt, width=width, height=height, seed=seed)
        await self.registry.store(
            project_id=project_id, asset_type=PRESENTER_ASSET_TYPE, content=data, ext=_sniff_image_ext(data),
            created_by=VIDEO_AGENT_ID, metadata={"prompt": prompt, "renderer": provider.name}, source=provider.name,
        )
        return data

    @staticmethod
    def _summary(shot, row, record, *, cached: bool) -> dict[str, Any]:
        return {
            "video_generation_id": record.id,
            "shot_id": shot.id,
            "shot_index": shot.shot_index,
            "version": row.version,
            "status": row.status,
            "idempotency_key": record.idempotency_key,
            "cached": cached,
            "candidates": record.candidates,
            "asset_id": str(record.asset_id),
        }

    # -- Gateway executor (Video agent) ------------------------------------

    async def tool_generate_video_shot(self, arguments: dict[str, Any]) -> dict[str, Any]:
        shot = await self.shots.get(arguments["shot_id"])
        project = await self.projects.get(shot.project_id) if shot else None
        image_provider = image_provider_for(project)
        video_provider = get_video_provider(
            project.video_provider if project else None,
            llm_provider=project.llm_provider if project else None,
        )

        summary = await self.generate(
            arguments["shot_id"],
            physics_proxy_asset_id=arguments["physics_proxy_asset_id"],
            idempotency_key=arguments.get("idempotency_key"),
            prompt_override=arguments.get("prompt"),
        )
        model_tag = f"video-gen:{image_provider.name}" if image_provider else "video-gen:MOCK"
        if video_provider is not None:
            model_tag += f"+{video_provider.name}"
        result = {**summary, "model": model_tag}
        if summary.get("clip_cost_usd"):
            # Picked up by dispatch_and_audit for the audit row / budget.
            result["cost_usd"] = summary["clip_cost_usd"]
        return result
