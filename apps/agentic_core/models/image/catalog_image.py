"""Image models from the AVOS model catalog (catalog.json): Z-Image, Qwen-Image, FLUX.1 schnell.

Each runs on your GPU server (ComfyUI, free per call) when its workflow is exported, else on Cloudflare's free tier
(FLUX only), else on fal.ai (paid). "best" picks the model per picture: Qwen-Image when the picture must show
readable text, Z-Image otherwise; if that model can't run or fails, the next ready one is tried, and with nothing
set up it falls back to the free image chain (Cloudflare -> Pollinations -> your image server).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agentic_core.models import catalog, fal_client
from agentic_core.models.image.base import ImageProvider

logger = logging.getLogger(__name__)

NEGATIVE = "blurry, low quality, distorted, deformed hands, extra limbs, watermark"
# fal input per model: default steps and extras (fal.ai/models/<endpoint>/api).
FAL_INPUTS = {
    "z-image": {"num_inference_steps": 8, "output_format": "png"},
    "qwen-image": {"num_inference_steps": 30, "guidance_scale": 2.5, "negative_prompt": NEGATIVE, "output_format": "png"},
    "flux-schnell": {"num_inference_steps": 4, "output_format": "png"},
}
COMFY_STEPS = {"z-image": 8, "qwen-image": 30, "flux-schnell": 4}


def fit_size(width: int, height: int, *, long_side: int = 1280, multiple: int = 16) -> tuple[int, int]:
    """Scale to a sensible generation size (long side ~1280) keeping the aspect, multiples of 16."""
    scale = long_side / max(width, height, 1)
    w = max(multiple, round(width * scale / multiple) * multiple)
    h = max(multiple, round(height * scale / multiple) * multiple)
    return int(w), int(h)


def fal_image_input(model_id: str, prompt: str, width: int, height: int, seed: int | None) -> dict:
    w, h = fit_size(width, height)
    data = {"prompt": prompt, "image_size": {"width": w, "height": h}, "num_images": 1,
            **FAL_INPUTS.get(model_id, {})}
    if seed is not None:
        data["seed"] = int(seed) % 2_147_483_647
    return data


class CatalogImageProvider(ImageProvider):
    """One catalog image model. Where it runs (a GPU worker, your ComfyUI server, Cloudflare, fal.ai) is decided by
    the Model Router per call, or fixed by `placement` when the "best" provider already chose it."""

    def __init__(self, model_id: str, placement: Any = None) -> None:
        self.model = catalog.get(model_id)
        if self.model["task"] != "image":
            raise ValueError(f"'{model_id}' is a {self.model['task']} model, not an image model.")
        self.model_id = model_id
        self.name = model_id
        self.last_backend: str | None = None
        self.placement = placement
        self.last_placement: Any = None

    def backend(self) -> str:
        return catalog.backend_for(self.model_id)

    async def generate(self, prompt: str, *, width: int = 512, height: int = 512, seed: int | None = None) -> bytes:
        from agentic_core.model_fabric import router

        if self.placement is not None:
            placements = [self.placement]
        else:
            plan = await router.plan(router.RouteRequest(task="image", width=width, height=height, prompt=prompt,
                                                         models=[self.model_id]))
            placements = plan.placements
            if not placements:
                why = "; ".join(f"{r.get('worker') or r['backend']}: {r['why']}" for r in plan.rejected) or "no backend is set up"
                raise catalog.ModelUnavailable(f"{self.model['name']} can't run now: {why}")
        errors: list[str] = []
        for i, pl in enumerate(placements):
            try:
                return await self._run(pl, prompt, width=width, height=height, seed=seed)
            except catalog.ModelUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 - next place this model can run
                if i == len(placements) - 1:
                    if errors:
                        raise RuntimeError(f"{self.model['name']} failed everywhere: {' | '.join(errors + [f'{pl.where}: {exc}'])}") from exc
                    raise
                logger.warning("%s on %s failed (%s), trying %s", self.model_id, pl.where, exc, placements[i + 1].where)
                errors.append(f"{pl.where}: {exc}")
        raise RuntimeError(f"{self.model['name']}: nowhere to run it.")

    async def _run(self, pl: Any, prompt: str, *, width: int, height: int, seed: int | None) -> bytes:
        from agentic_core.model_fabric import scheduler, telemetry

        self.last_backend = pl.backend
        self.last_placement = pl
        w, h = fit_size(width, height)
        async with telemetry.track(pl, task="image", units=max(0.25, w * h / 1_000_000)) as job:
            if pl.backend == "gpu":
                return await scheduler.run_on_worker(
                    pl, job, prompt=prompt, negative_prompt=NEGATIVE, width=w, height=h, seed=seed,
                    steps=COMFY_STEPS.get(self.model_id), want="image",
                    timeout=float(os.getenv("GPU_IMAGE_TIMEOUT") or 600))
            await job.started()
            if pl.backend == "fal":
                job.cost_usd = pl.est_cost
                result = await fal_client.run(self.model["fal"]["endpoint"],
                                              fal_image_input(self.model_id, prompt, width, height, seed),
                                              timeout=float(os.getenv("FAL_IMAGE_TIMEOUT") or 300))
                url = fal_client.first_url(result, "images", "image")
                if not url:
                    raise fal_client.FalError(f"fal.ai {self.model['name']} returned no image.")
                return await fal_client.download(url)
            job.cost_usd = 0.0
            if pl.backend == "comfyui":
                from agentic_core.models.video.comfyui_provider import ComfyUIVideoProvider

                runner = ComfyUIVideoProvider(os.environ["COMFYUI_URL"], str(catalog.workflow_path(self.model_id)),
                                              negative_prompt=NEGATIVE,
                                              timeout=float(os.getenv("COMFYUI_TIMEOUT") or 1800))
                return await runner.run(prompt, width=w, height=h, seed=seed, steps=COMFY_STEPS.get(self.model_id),
                                        want="image")
            if pl.backend == "cloudflare":
                from agentic_core.models.image.cloudflare_provider import CloudflareImageProvider

                cf = CloudflareImageProvider(account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
                                             api_token=os.environ["CLOUDFLARE_API_TOKEN"],
                                             model=self.model["cloudflare"]["model"])
                return await cf.generate(prompt, width=width, height=height, seed=seed)
            raise catalog.ModelUnavailable(f"{self.model['name']}: unknown backend {pl.backend}.")


class BestImageProvider(ImageProvider):
    """The Model Router ranks every image model × place to run it for each picture (text in the picture → Qwen-Image,
    quality / speed / cost per the project's preference); falls back down that list, then to the free chain."""

    name = "best"

    def __init__(self, *, fast: bool = False) -> None:
        self.fast = fast
        self.last_model: str | None = None
        self.last_placement: Any = None

    def candidates(self, prompt: str) -> list[str]:
        first = catalog.route_image(prompt, fast=self.fast)
        rest = [m["id"] for m in sorted(catalog.models("image", include_custom=False), key=lambda m: m["rank"]) if m["id"] != first]
        return [first, *rest]

    async def generate(self, prompt: str, *, width: int = 512, height: int = 512, seed: int | None = None) -> bytes:
        from agentic_core.model_fabric import router

        req = router.RouteRequest(task="image", width=width, height=height, prompt=prompt,
                                  models=["flux-schnell"] if self.fast else None)
        plan = await router.plan(req)
        errors: list[str] = []
        for pl in plan.placements:
            try:
                p = CatalogImageProvider(pl.model, placement=pl)
                data = await p.generate(prompt, width=width, height=height, seed=seed)
                self.last_model = pl.model
                self.last_placement = pl
                return data
            except Exception as exc:  # noqa: BLE001 - try the next option, report all if none works
                logger.warning("best image: %s on %s failed (%s), trying the next option", pl.model, pl.where, exc)
                errors.append(f"{pl.model}@{pl.where}: {exc}")
        from agentic_core.models.image.factory import build_free_chain

        try:
            data = await build_free_chain().generate(prompt, width=width, height=height, seed=seed)
            self.last_model = "free"
            self.last_placement = None
            return data
        except Exception as exc:  # noqa: BLE001
            errors.append(f"free chain: {exc}")
            raise RuntimeError("No image model could make this picture. " + " | ".join(errors)) from exc
