"""Hugging Face Diffusers pipelines inside the worker process: models stay loaded between jobs (warm), and the
router's precision and attention choices are applied directly.

    precision  bf16 → plain bf16 weights
               fp8 / int8 / int4 → torchao weight-only quantization of the transformer (pip install torchao)
               fp4 / int4 → Nunchaku SVDQuant transformer when the model has one configured (pip install nunchaku)
    attention  sage / sage2 / flash → pipe.transformer.set_attention_backend(...) (diffusers ≥ 0.35), else PyTorch SDPA
    offload    enable_model_cpu_offload() when the model doesn't fit in VRAM

Models (Hugging Face repos) are listed in MODELS; add or override entries with WORKER_DIFFUSERS_MODELS_JSON, e.g.
{"wan-2.2": {"repo": "Wan-AI/Wan2.2-I2V-A14B-Diffusers", "kind": "i2v", "steps": 40, "guidance": 3.5}}.
Weights download on first use (set HF_HOME to a big disk; gated repos need HF_TOKEN).
"""
from __future__ import annotations

import asyncio
import io
import json
import tempfile
import threading
from pathlib import Path
from typing import Any

from worker import config, gpu
from worker.adapters.base import Adapter, JobSpec, Progress

MODELS: dict[str, dict[str, Any]] = {
    "flux-schnell": {"repo": "black-forest-labs/FLUX.1-schnell", "kind": "image", "steps": 4, "guidance": 0.0,
                     "nunchaku": "nunchaku-tech/nunchaku-flux.1-schnell"},
    "qwen-image": {"repo": "Qwen/Qwen-Image", "kind": "image", "steps": 30, "true_cfg_scale": 4.0},
    "z-image": {"repo": "Tongyi-MAI/Z-Image-Turbo", "kind": "image", "steps": 8, "guidance": 0.0},
    "wan-2.2": {"repo": "Wan-AI/Wan2.2-I2V-A14B-Diffusers", "kind": "i2v", "steps": 40, "guidance": 3.5,
                "components": ["transformer", "transformer_2"]},   # Wan 2.2 A14B: high- and low-noise experts
    "wan-vace": {"repo": "Wan-AI/Wan2.1-VACE-14B-diffusers", "kind": "vace", "steps": 30, "guidance": 5.0},
}
TORCHAO = {"fp8": "float8wo_e4m3", "int8": "int8wo", "int4": "int4wo"}
ATTENTION = {"sage2": "sage", "sage": "sage", "flash": "flash", "sdpa": "native"}


def models_table() -> dict[str, dict[str, Any]]:
    table = {k: dict(v) for k, v in MODELS.items()}
    if config.DIFFUSERS_MODELS_JSON and Path(config.DIFFUSERS_MODELS_JSON).is_file():
        for k, v in json.loads(Path(config.DIFFUSERS_MODELS_JSON).read_text("utf-8")).items():
            table[k] = {**table.get(k, {}), **v}
    if config.DIFFUSERS_MODELS:
        keep = {m.strip() for m in config.DIFFUSERS_MODELS.split(",")}
        table = {k: v for k, v in table.items() if k in keep}
    return table


class Cancelled(Exception):
    pass


class DiffusersAdapter(Adapter):
    name = "diffusers"
    attentions = ("sage2", "sage", "flash", "sdpa")
    offload = True

    def __init__(self) -> None:
        self.pipes: dict[str, Any] = {}
        self._cancel = threading.Event()

    @property
    def precisions(self) -> tuple[str, ...]:  # type: ignore[override]
        sup = gpu.supports()
        out = ["bf16"]
        if sup.get("torchao"):
            out += [p for p in ("fp8", "int8", "int4") if p != "fp8" or sup.get("fp8")]
        if sup.get("nunchaku"):
            out += [p for p in ("fp4", "int4") if p not in out and (p != "fp4" or sup.get("fp4"))]
        return tuple(out)

    async def ready(self) -> tuple[bool, str | None]:
        sup = gpu.supports()
        if not sup.get("torch"):
            return False, "PyTorch isn't installed (pip install -r requirements-diffusers.txt)."
        try:
            import importlib.util
            if importlib.util.find_spec("diffusers") is None:
                return False, "diffusers isn't installed (pip install -r requirements-diffusers.txt)."
        except ImportError:
            return False, "diffusers isn't installed."
        if not sup.get("cuda"):
            return False, "No NVIDIA GPU found."
        return True, None

    def models(self) -> list[str]:
        return sorted(models_table())

    # ---- loading ----
    def _load_sync(self, job: JobSpec) -> Any:
        import torch
        from diffusers import DiffusionPipeline

        spec = models_table()[job.model]
        kwargs: dict[str, Any] = {"torch_dtype": torch.bfloat16}
        if job.precision in ("fp4", "int4") and spec.get("nunchaku") and gpu.supports().get("nunchaku"):
            import nunchaku  # noqa: F401
            from nunchaku import NunchakuFluxTransformer2dModel

            kwargs["transformer"] = NunchakuFluxTransformer2dModel.from_pretrained(spec["nunchaku"])
        elif job.precision in TORCHAO:
            from diffusers import PipelineQuantizationConfig

            kwargs["quantization_config"] = PipelineQuantizationConfig(
                quant_backend="torchao", quant_kwargs={"quant_type": TORCHAO[job.precision]},
                components_to_quantize=spec.get("components") or ["transformer"])
        pipe = DiffusionPipeline.from_pretrained(spec["repo"], **kwargs)
        if job.offload:
            pipe.enable_model_cpu_offload()
        else:
            pipe.to("cuda")
        backend = ATTENTION.get(job.attention, "native")
        for name in ("transformer", "transformer_2"):
            t = getattr(pipe, name, None)
            if t is not None and hasattr(t, "set_attention_backend") and backend != "native":
                try:
                    t.set_attention_backend(backend)
                except Exception:  # noqa: BLE001 - stay on SDPA
                    pass
        return pipe

    async def load(self, job: JobSpec, progress: Progress) -> None:
        if job.model in self.pipes:
            return
        await progress(0.0, f"loading {job.model} ({job.precision}{', offload' if job.offload else ''})")
        self.pipes[job.model] = await asyncio.to_thread(self._load_sync, job)

    async def unload(self, model: str) -> None:
        pipe = self.pipes.pop(model, None)
        if pipe is None:
            return
        del pipe
        try:
            import gc

            import torch

            gc.collect()
            torch.cuda.empty_cache()
        except ImportError:
            pass

    # ---- running ----
    def _run_sync(self, job: JobSpec, report: Any) -> tuple[bytes, str]:
        import torch
        from PIL import Image

        pipe = self.pipes[job.model]
        spec = models_table()[job.model]
        steps = int(job.steps or spec.get("steps") or 30)
        gen = torch.Generator("cuda").manual_seed(int(job.seed or 0))

        def on_step(_pipe: Any, i: int, _t: Any, kw: dict[str, Any]) -> dict[str, Any]:
            if self._cancel.is_set():
                raise Cancelled()
            report((i + 1) / steps, f"step {i + 1}/{steps}")
            return kw

        common = {"prompt": job.prompt, "num_inference_steps": steps, "generator": gen, "callback_on_step_end": on_step,
                  "width": job.width - job.width % 16, "height": job.height - job.height % 16}
        kind = spec.get("kind", "image")
        if kind == "image":
            extra: dict[str, Any] = {}
            if "true_cfg_scale" in spec:
                extra.update(true_cfg_scale=spec["true_cfg_scale"], negative_prompt=job.negative_prompt or " ")
            elif "guidance" in spec:
                extra["guidance_scale"] = spec["guidance"]
            img = pipe(**common, **extra).images[0]
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue(), "png"
        from diffusers.utils import export_to_video

        ref = Image.open(io.BytesIO(job.inputs["image"])).convert("RGB") if job.inputs.get("image") else None
        frames_n = int(job.frames or round(job.seconds * (job.fps or 16)) + 1)
        args = {**common, "negative_prompt": job.negative_prompt, "num_frames": frames_n,
                "guidance_scale": spec.get("guidance", 5.0)}
        if kind == "i2v":
            if ref is None:
                raise RuntimeError(f"{job.model} animates a picture and the job has none.")
            args["image"] = ref.resize((args["width"], args["height"]))
        elif kind == "vace" and ref is not None:
            args["reference_images"] = [ref]
        frames = pipe(**args).frames[0]
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "clip.mp4"
            export_to_video(frames, str(out), fps=int(job.fps or 16))
            return out.read_bytes(), "mp4"

    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        self._cancel.clear()
        loop = asyncio.get_running_loop()

        def report(frac: float, step: str) -> None:
            asyncio.run_coroutine_threadsafe(progress(frac, step), loop)

        try:
            return await asyncio.to_thread(self._run_sync, job, report)
        except Cancelled as exc:
            raise asyncio.CancelledError() from exc

    async def cancel(self) -> None:
        self._cancel.set()
