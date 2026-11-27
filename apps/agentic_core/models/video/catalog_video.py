"""Video and avatar models from the AVOS model catalog (catalog.json).

    wan-2.2          image -> video, every shot (default)
    ltx-2.3          image -> video for long shots; image + narration audio -> video when audio is given
    wan-vace         reference/control -> video (continuity; depth re-style when a driving video is given)
    longcat-avatar   presenter portrait + narration audio -> talking presenter
    infinitetalk     presenter portrait + narration audio -> long talking video
    wan-2.2-animate  character image + driving video -> the character performs the motion
    scail-2          same job as wan-2.2-animate, your GPU server only

Each can run on your GPU workers (Model Fabric: the router picks worker, backend and precision), on your ComfyUI
server when its workflow is exported to COMFYUI_WORKFLOW_DIR/<model id>.json, or on fal.ai (FAL_KEY). The "best"
and "avatar" providers ask the Model Router to rank every model and place for each shot and fall back down that
list; "best" ends at the free motion provider (still image + camera move) when nothing is set up.
"""
from __future__ import annotations

import json
import logging
import math
import os
from typing import Any

from agentic_core.models import catalog, fal_client
from agentic_core.models.video.base import VideoProvider

logger = logging.getLogger(__name__)

NEGATIVE = "blur, distort, low quality, extra limbs, deformed hands, flicker, text, watermark"

# fps / frame rule (4k+1 for Wan, 8k+1 for LTX) / frame limits / what the model needs.
SPEC: dict[str, dict[str, Any]] = {
    "wan-2.2": {"fps": 16, "multiple": 4, "min": 17, "max": 161, "image": "required"},
    "ltx-2.3": {"fps": 25, "multiple": 8, "min": 9, "max": 481, "image": "required", "audio": "optional"},
    "wan-vace": {"fps": 16, "multiple": 4, "min": 81, "max": 241, "video": "optional"},
    "longcat-avatar": {"fps": 25, "multiple": 4, "min": 41, "max": 721, "image": "required", "audio": "required", "presenter": True},
    "infinitetalk": {"fps": 25, "multiple": 4, "min": 41, "max": 721, "image": "required", "audio": "required", "presenter": True},
    "wan-2.2-animate": {"fps": 16, "multiple": 4, "min": 17, "max": 241, "image": "required", "video": "required"},
    "scail-2": {"fps": 16, "multiple": 4, "min": 17, "max": 241, "image": "required", "video": "required"},
}
# fal.ai price per second of video (catalog.json has the wording), for the cost shown on the project.
PRICE_PER_SECOND = {"wan-2.2": 0.08, "ltx-2.3": 0.08, "wan-vace": 0.08, "longcat-avatar": 0.15,
                    "infinitetalk": 0.20, "wan-2.2-animate": 0.08}


def frames_for(model_id: str, seconds: float) -> int:
    s = SPEC[model_id]
    wanted = max(s["min"], round(seconds * s["fps"]) + 1)
    k = math.ceil((wanted - 1) / s["multiple"])
    frames = k * s["multiple"] + 1
    while frames > s["max"]:
        frames -= s["multiple"]
    return max(frames, s["min"])


def aspect(width: int, height: int) -> str:
    if abs(width - height) < 8:
        return "1:1"
    return "9:16" if height > width else "16:9"


def _env(model_id: str, what: str, default: str) -> str:
    return os.getenv(f"{model_id.upper().replace('-', '_').replace('.', '_')}_{what}") or default


def fal_video_input(model_id: str, *, prompt: str, width: int, height: int, seed: int | None, seconds: float,
                    image: str | None, audio: str | None, video: str | None) -> tuple[str, dict[str, Any]]:
    """(endpoint, input) for this model on fal.ai. <MODEL>_FAL_INPUT_JSON (e.g. WAN_2_2_FAL_INPUT_JSON) adds/overrides fields."""
    m = catalog.get(model_id)
    if not m.get("fal"):
        raise catalog.ModelUnavailable(f"{m['name']} has no hosted API; run it on your GPU server (ComfyUI).")
    endpoint = m["fal"]["endpoint"]
    seed_v = None if seed is None else int(seed) % 2_147_483_647
    data: dict[str, Any] = {"prompt": prompt}
    if model_id == "wan-2.2":
        data.update(image_url=image, num_frames=frames_for(model_id, seconds), frames_per_second=16,
                    resolution=_env(model_id, "RESOLUTION", "720p"), aspect_ratio="auto", negative_prompt=NEGATIVE)
    elif model_id == "ltx-2.3":
        if audio:   # follow the narration: the clip's length and motion come from the audio
            endpoint = m["fal"]["audio_endpoint"]
            data.update(audio_url=audio, image_url=image, match_audio_length=True)
        else:
            data.update(image_url=image, duration=next((d for d in (6, 8, 10) if seconds <= d + 0.5), 10),
                        resolution=_env(model_id, "RESOLUTION", "1080p"), aspect_ratio="auto", generate_audio=False)
    elif model_id == "wan-vace":
        data.update(num_frames=frames_for(model_id, seconds), resolution=_env(model_id, "RESOLUTION", "720p"),
                    aspect_ratio=aspect(width, height), negative_prompt=NEGATIVE)
        if image:
            data.update(ref_image_urls=[image], first_frame_url=image)
        if video:
            data.update(video_url=video, task="depth")
    elif model_id == "longcat-avatar":
        data.update(image_url=image, audio_url=audio, negative_prompt=NEGATIVE,
                    resolution=_env(model_id, "RESOLUTION", "480p"),
                    num_segments=min(10, max(1, math.ceil(seconds / 5.0))))
    elif model_id == "infinitetalk":
        data.update(image_url=image, audio_url=audio, num_frames=frames_for(model_id, seconds),
                    resolution=_env(model_id, "RESOLUTION", "480p"))
    elif model_id == "wan-2.2-animate":
        data = {"video_url": video, "image_url": image, "resolution": _env(model_id, "RESOLUTION", "480p")}
    else:
        raise catalog.ModelUnavailable(f"{m['name']} has no hosted API; run it on your GPU server (ComfyUI).")
    if seed_v is not None:
        data["seed"] = seed_v
    extra = os.getenv(f"{model_id.upper().replace('-', '_').replace('.', '_')}_FAL_INPUT_JSON")
    if extra:
        try:
            data.update(json.loads(extra))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{model_id} FAL_INPUT_JSON is not valid JSON.") from exc
    return endpoint, {k: v for k, v in data.items() if v is not None}


class CatalogVideoProvider(VideoProvider):
    """One catalog video/avatar model. Where it runs (a GPU worker, your ComfyUI server, fal.ai) is decided by the
    Model Router per call, or fixed by `placement` when a "best" provider already chose it."""

    def __init__(self, model_id: str, placement: Any = None) -> None:
        self.model = catalog.get(model_id)
        if model_id not in SPEC:
            raise ValueError(f"'{model_id}' is not a video model.")
        self.model_id = model_id
        self.name = model_id
        spec = SPEC[model_id]
        self.wants_audio: str | None = spec.get("audio")          # "required" / "optional" / None
        self.needs_presenter: bool = bool(spec.get("presenter"))  # a portrait instead of the shot picture
        self.needs_video: str | None = spec.get("video")
        self.cost_per_clip_usd = PRICE_PER_SECOND.get(model_id, 0.0) * 5
        self.last_backend: str | None = None
        self.placement = placement
        self.last_placement: Any = None

    async def _placements(self, seconds: float, width: int, height: int, has_audio: bool) -> list[Any]:
        from agentic_core.model_fabric import router

        task = "avatar" if self.model["task"] == "avatar" else "video"
        plan = await router.plan(router.RouteRequest(task=task, seconds=seconds, width=width, height=height,
                                                     has_audio=has_audio, models=[self.model_id]))
        if not plan.placements:
            why = "; ".join(f"{r.get('worker') or r['backend']}: {r['why']}" for r in plan.rejected) or "no backend is set up"
            raise catalog.ModelUnavailable(f"{self.model['name']} can't run now: {why}")
        return plan.placements

    async def generate(self, prompt: str, *, width: int = 512, height: int = 512, seed: int | None = None,
                       duration_seconds: float = 4.0, image: bytes | None = None, audio: bytes | None = None,
                       video: bytes | None = None) -> bytes:
        spec = SPEC[self.model_id]
        name = self.model["name"]
        if spec.get("image") == "required" and not image:
            raise RuntimeError(f"{name} animates a picture, but this shot has none. Pick an image model for the project.")
        if spec.get("audio") == "required" and not audio:
            raise RuntimeError(f"{name} needs the narration audio for this shot, and none was found.")
        if spec.get("video") == "required" and not video:
            raise RuntimeError(f"{name} needs a driving video.")
        placements = [self.placement] if self.placement is not None else \
            await self._placements(duration_seconds, width, height, bool(audio))
        errors: list[str] = []
        for i, pl in enumerate(placements):
            try:
                return await self._run(pl, prompt, width=width, height=height, seed=seed,
                                       duration_seconds=duration_seconds, image=image, audio=audio, video=video)
            except catalog.ModelUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 - next place this model can run
                if i == len(placements) - 1:
                    if errors:
                        raise RuntimeError(f"{name} failed everywhere: {' | '.join(errors + [f'{pl.where}: {exc}'])}") from exc
                    raise
                logger.warning("%s on %s failed (%s), trying %s", self.model_id, pl.where, exc, placements[i + 1].where)
                errors.append(f"{pl.where}: {exc}")
        raise RuntimeError(f"{name}: nowhere to run it.")

    async def _run(self, pl: Any, prompt: str, *, width: int, height: int, seed: int | None, duration_seconds: float,
                   image: bytes | None, audio: bytes | None, video: bytes | None) -> bytes:
        from agentic_core.model_fabric import scheduler, telemetry

        spec = SPEC[self.model_id]
        name = self.model["name"]
        self.last_backend = pl.backend
        self.last_placement = pl
        task = "avatar" if self.model["task"] == "avatar" else "video"
        async with telemetry.track(pl, task=task, units=max(1.0, duration_seconds)) as job:
            if pl.backend == "gpu":
                data = await scheduler.run_on_worker(
                    pl, job, prompt=prompt, negative_prompt=NEGATIVE, width=width, height=height,
                    seconds=duration_seconds, seed=seed, want="video",
                    frames=frames_for(self.model_id, duration_seconds), fps=spec["fps"],
                    inputs={"image": image, "audio": audio, "video": video},
                    timeout=_timeout(float(os.getenv("GPU_JOB_TIMEOUT") or 1800)))
                self.cost_per_clip_usd = job.cost_usd if job.cost_usd is not None else pl.est_cost
                return data
            await job.started()
            if pl.backend == "comfyui":
                from agentic_core.models.video.comfyui_provider import ComfyUIVideoProvider

                runner = ComfyUIVideoProvider(
                    os.environ["COMFYUI_URL"], str(catalog.workflow_path(self.model_id)), fps=spec["fps"],
                    frame_multiple=spec["multiple"], max_frames=spec["max"], negative_prompt=NEGATIVE,
                    timeout=_timeout(float(os.getenv("COMFYUI_TIMEOUT") or 1800)))
                self.cost_per_clip_usd = 0.0
                job.cost_usd = 0.0
                return await runner.run(prompt, width=width, height=height, seed=seed, duration_seconds=duration_seconds,
                                        files={"{{IMAGE}}": image, "{{AUDIO}}": audio, "{{VIDEO}}": video})
            if pl.backend != "fal":
                raise catalog.ModelUnavailable(f"{name} can't run on {pl.backend}.")
            uri = lambda b: fal_client.data_uri(b) if b else None  # noqa: E731
            endpoint, data = fal_video_input(self.model_id, prompt=prompt, width=width, height=height, seed=seed,
                                             seconds=duration_seconds, image=uri(image), audio=uri(audio), video=uri(video))
            self.cost_per_clip_usd = round(PRICE_PER_SECOND.get(self.model_id, 0.0) * max(duration_seconds, 1.0), 4)
            job.cost_usd = self.cost_per_clip_usd
            result = await fal_client.run(endpoint, data, timeout=_timeout(float(os.getenv("FAL_VIDEO_TIMEOUT") or 1200)))
            url = fal_client.first_url(result, "video", "videos")
            if not url:
                raise fal_client.FalError(f"fal.ai {name} returned no video.")
            return await fal_client.download(url)


def _timeout(default: float) -> float:
    """The shot's time limit (Model Fabric policy) caps how long one run may take."""
    from agentic_core.model_fabric import policy

    limit = policy.current().max_seconds_per_shot
    return min(default, float(limit)) if limit else default


class BestVideoProvider(VideoProvider):
    """kind="video" / "avatar": the Model Router ranks every model × place to run it (GPU workers, your ComfyUI,
    fal.ai) for each shot and the provider tries them in order; "video" ends with the free motion provider."""

    def __init__(self, kind: str = "video") -> None:
        self.kind = kind
        self.name = "best" if kind == "video" else "avatar"
        self.wants_audio = "required" if kind == "avatar" else None
        self.needs_presenter = kind == "avatar"
        self.needs_video = None
        self.cost_per_clip_usd = 0.0
        self.last_model: str | None = None
        self.last_placement: Any = None

    def candidates(self, seconds: float) -> list[str]:
        if self.kind == "avatar":
            first = catalog.route_avatar(seconds=seconds)
            return [first, *[m for m in ("longcat-avatar", "infinitetalk") if m != first]]
        first = catalog.route_video(seconds=seconds)
        return [first, *[m for m in ("wan-2.2", "ltx-2.3") if m != first]]

    def ready(self, seconds: float = 5.0) -> list[str]:
        out = []
        for m in self.candidates(seconds):
            try:
                catalog.backend_for(m)
                out.append(m)
            except catalog.ModelUnavailable:
                pass
        return out

    async def generate(self, prompt: str, *, width: int = 512, height: int = 512, seed: int | None = None,
                       duration_seconds: float = 4.0, image: bytes | None = None, audio: bytes | None = None,
                       video: bytes | None = None) -> bytes:
        from agentic_core.model_fabric import router

        plan = await router.plan(router.RouteRequest(task=self.kind, seconds=duration_seconds, width=width,
                                                     height=height, prompt=prompt, has_audio=bool(audio)))
        errors: list[str] = []
        for pl in plan.placements:
            p = CatalogVideoProvider(pl.model, placement=pl)
            try:
                clip = await p.generate(prompt, width=width, height=height, seed=seed, duration_seconds=duration_seconds,
                                        image=image, audio=audio if p.wants_audio else None)
                self.last_model = pl.model
                self.last_placement = pl
                self.name = f"{'best' if self.kind == 'video' else 'avatar'}:{pl.model}"
                self.cost_per_clip_usd = p.cost_per_clip_usd
                return clip
            except Exception as exc:  # noqa: BLE001 - next placement
                logger.warning("%s: %s on %s failed (%s), trying the next option", self.name, pl.model, pl.where, exc)
                errors.append(f"{pl.model}@{pl.where}: {exc}")
        if self.kind == "avatar":
            limits = "; ".join(f"{r['model']}@{r.get('worker') or r['backend']}: {r['why']}" for r in plan.rejected[:6])
            raise RuntimeError("No avatar model could make this shot. " + (" | ".join(errors) or limits or
                               "Set FAL_KEY, add a GPU worker, or export the LongCat / InfiniteTalk workflow to your GPU server."))
        from agentic_core.models.video.motion_provider import MotionVideoProvider

        if errors:
            logger.warning("best video: every AI option failed (%s); using the free motion provider", " | ".join(errors))
        self.last_model = "motion"
        self.last_placement = None
        self.name = "best:motion"
        self.cost_per_clip_usd = 0.0
        return await MotionVideoProvider().generate(prompt, width=width, height=height, seed=seed,
                                                    duration_seconds=duration_seconds, image=image)
