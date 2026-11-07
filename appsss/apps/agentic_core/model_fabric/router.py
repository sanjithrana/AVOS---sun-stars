"""The Model Router: which model, on which GPU (or hosted API), at which precision, for this shot.

It doesn't ask "what is the best model?" but scores every way the job could run:

    task (image / video / avatar) → candidate models (catalog + your models)
      → every place each can run: each online GPU worker × backend (ComfyUI / Wan2GP / Diffusers) × precision that
        fits its VRAM, plus your ComfyUI server, Cloudflare and fal.ai / Replicate
      → hard checks: the GPU has enough VRAM (or can offload), supports the precision, the limits allow the cost/time
      → estimate: quality (model + fit for this shot + precision + measured QA), time (GPU speed × attention kernel ×
        precision + model load unless already loaded + queue wait), cost (GPU $/h or hosted price)
      → score by the project's preference (quality / balanced / speed / cost) → ranked placements, with reasons.

`route()` is pure (no network): give it the worker statuses. `plan()` fetches them first.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

from agentic_core.model_fabric import dispatch, performance, requirements as R
from agentic_core.model_fabric.policy import GenerationPolicy, current
from agentic_core.model_fabric.workers import WorkerStatus

WEIGHTS = {"quality": (0.7, 0.15, 0.15), "balanced": (0.5, 0.25, 0.25), "speed": (0.3, 0.55, 0.15),
           "cost": (0.3, 0.15, 0.55)}
HOSTED_PAID = ("fal", "replicate")


@dataclass
class RouteRequest:
    task: str = "video"                 # image | video | avatar
    seconds: float = 5.0
    width: int = 1280
    height: int = 720
    prompt: str = ""
    needs_text: bool | None = None      # None: detect from the prompt (images)
    has_audio: bool = False             # the clip should follow the narration
    continuity: bool = False            # keep identity/look from a reference (repairs)
    speakers: int = 1
    models: list[str] | None = None     # only these models (a project that picked one)


@dataclass
class Placement:
    model: str
    model_name: str
    backend: str                        # gpu | comfyui | cloudflare | fal | replicate
    worker_id: str | None = None
    worker_name: str | None = None
    gpu: str | None = None
    adapter: str | None = None          # comfyui | wan2gp | diffusers | mock (on a GPU worker)
    precision: str | None = None
    attention: str | None = None
    offload: bool = False
    warm: bool = False
    vram_gb: float | None = None
    est_seconds: float = 0.0
    est_cost: float = 0.0
    quality: float = 0.0
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def where(self) -> str:
        return self.gpu if self.backend == "gpu" and self.gpu else self.backend

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["where"] = self.where
        return d

    def label(self) -> str:
        if self.backend == "gpu":
            return f"{self.model_name} · {self.worker_name} ({self.gpu}) · {self.adapter} · {self.precision}"
        return f"{self.model_name} · {self.backend}"


@dataclass
class RoutePlan:
    request: RouteRequest
    policy: GenerationPolicy
    placements: list[Placement]
    rejected: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {"request": asdict(self.request), "policy": self.policy.as_dict(),
                "placements": [p.as_dict() for p in self.placements], "rejected": self.rejected}


# ---------- candidates ----------
def candidate_models(req: RouteRequest) -> list[dict[str, Any]]:
    from agentic_core.models import catalog

    if req.models:
        out = []
        for mid in req.models:
            try:
                out.append(catalog.get(mid))
            except KeyError:
                continue
        return out
    if req.task == "image":
        return catalog.models("image")
    if req.task == "avatar":
        return [m for m in catalog.models("avatar") if m["id"] in ("longcat-avatar", "infinitetalk") or m.get("custom")]
    ids = ["wan-2.2", "ltx-2.3"] + (["wan-vace"] if req.continuity else [])
    return [catalog.get(i) for i in ids] + [m for m in catalog.models("video") if m.get("custom")]


def fit_quality(model: dict[str, Any], fabric: dict[str, Any], req: RouteRequest) -> tuple[float, list[str]]:
    """The model's quality for THIS shot: its base quality adjusted by what the shot needs."""
    from agentic_core.models import catalog

    q, why = float(fabric["quality"]), []
    s = set(fabric.get("strengths") or [])
    if req.task == "image":
        text = catalog.needs_text(req.prompt) if req.needs_text is None else req.needs_text
        if text:
            q += 0.12 if "text" in s else -0.2   # wrong or garbled text ruins the picture
            why.append("readable text in the picture" + (" (its strength)" if "text" in s else " (not its strength)"))
    elif req.task == "video":
        if req.has_audio:
            q += 0.1 if "audio" in s else 0.0
            if "audio" in s:
                why.append("follows the narration audio")
        if req.seconds > 10.5:
            q += 0.08 if "long" in s else -0.08
            why.append(f"long shot ({req.seconds:.0f} s)" + ("" if "long" in s else ": beyond its usual length"))
        if req.continuity:
            q += 0.15 if "continuity" in s else -0.05
            if "continuity" in s:
                why.append("keeps look and identity (continuity)")
    elif req.task == "avatar":
        if req.speakers > 1 or req.seconds > 20:
            ok = bool(s & {"long", "multi_speaker"})
            q += 0.1 if ok else -0.08
            why.append("long / multi-speaker take" + ("" if ok else ": not its strength"))
    return q, why


def _units(req: RouteRequest) -> float:
    if req.task == "image":
        return max(0.25, req.width * req.height / 1_000_000)
    return max(1.0, req.seconds)


# ---------- placements ----------
def _gpu_placements(model: dict[str, Any], fabric: dict[str, Any], req: RouteRequest, st: WorkerStatus,
                    rejected: list[dict[str, Any]]) -> list[Placement]:
    out: list[Placement] = []
    mid = model["id"]
    adapters = st.can_run(mid)
    if not adapters:
        return out
    total = float(st.gpu.get("vram_gb") or 0)
    free = float(st.gpu.get("free_vram_gb") if st.gpu.get("free_vram_gb") is not None else total)
    native = R.supported_precisions(st.supports)
    loaded = {(x.get("model"), x.get("adapter")): x for x in st.loaded}
    coming = dispatch.on_the_way(st.id)      # models this process already sent jobs for: loaded by the time we run
    units = _units(req)
    for adapter in adapters:
        info = st.adapters[adapter]
        precs = [p for p in R.PRECISIONS if p in (info.get("precisions") or ["bf16"]) and p in native]
        if st.gpu.get("device") == "cpu":   # a CPU computes in bf16 anyway: the smallest weights page least from the SSD
            precs.sort(key=lambda p: R.vram_need(fabric, p) or 1e9)
        if not precs:
            rejected.append({"model": mid, "backend": "gpu", "worker": st.name, "adapter": adapter,
                             "why": "none of its precisions run natively on this GPU"})
            continue
        warm = loaded.get((mid, adapter))
        if not warm and (mid, adapter) in coming:
            warm = {"model": mid, "adapter": adapter, "precision": coming[(mid, adapter)], "coming": True}
        chosen, offload = None, False
        if warm and warm.get("precision") in precs:
            chosen = warm["precision"]
        has_table = bool(fabric.get("vram_gb"))
        if chosen is None:
            if not has_table:
                chosen = precs[0]
            else:
                for p in precs:
                    need = R.vram_need(fabric, p)
                    if need is not None and need <= total - R.RESERVE_GB:
                        chosen = p
                        break
        if chosen is None:
            smallest = min(precs, key=lambda p: R.vram_need(fabric, p) or 1e9)
            if fabric.get("min_vram_gb") and float(fabric["min_vram_gb"]) <= total and info.get("offload", True):
                chosen, offload = smallest, True
            else:
                need = min((R.vram_need(fabric, p) or 0) for p in precs) or fabric.get("min_vram_gb")
                mem = "memory (RAM + page file: make the page file bigger)" if st.gpu.get("device") == "cpu" else "VRAM"
                rejected.append({"model": mid, "backend": "gpu", "worker": st.name, "adapter": adapter,
                                 "why": f"needs about {need:.0f} GB {mem}, {st.gpu.get('name') or 'this GPU'} has {total:.0f} GB"})
                continue
        attention = info.get("attention") or "sdpa"
        speed = R.gpu_speed(st.gpu.get("name"))
        gpu_time = float(fabric["speed"]) * units * R.PRECISION_SPEED.get(chosen, 1.0) * R.ATTENTION_SPEED.get(attention, 1.0) / speed
        if offload:
            gpu_time *= R.OFFLOAD_SLOWDOWN
        reasons = []
        learned = performance.lookup(mid, st.gpu.get("name") or "gpu")
        if learned and learned.get("unit_seconds"):
            gpu_time = float(learned["unit_seconds"]) * units
            reasons.append(f"speed measured over {learned['runs']} runs")
        need = R.vram_need(fabric, chosen) or 0
        load = 0.0 if warm else float(fabric["load_seconds"]) * (1.0 if need <= free else 1.25)
        reported = st.queue_depth * float(st.report.get("avg_job_seconds") or (20 if req.task == "image" else 180))
        wait = max(reported, dispatch.pending_seconds(st.id, before_priority=dispatch.current_priority()))
        est = gpu_time + load + wait
        cost = st.cost_per_hour * (gpu_time + load) / 3600.0
        if st.gpu.get("device") == "cpu":
            reasons.append(f"{st.gpu.get('name')}: {st.gpu.get('ram_gb', 0):.0f} GB RAM + {st.gpu.get('swap_gb', 0):.0f} GB page file, "
                           f"drawn at ≤{st.gpu.get('max_side') or 512}px (slow, free)")
        else:
            reasons.append(f"{st.gpu.get('name') or 'GPU'} {total:.0f} GB, {chosen}" + (" with CPU offload (slow)" if offload else ""))
        reasons.append(("loading for an earlier shot" if warm.get("coming") else "already loaded") if warm
                       else f"loads in ~{load:.0f} s")
        if attention != "sdpa":
            reasons.append(f"{attention} attention")
        if wait > 1:
            ahead = max(st.queue_depth, len(dispatch.inflight(st.id)))
            reasons.append(f"{ahead} job(s) ahead (~{wait:.0f} s)")
        out.append(Placement(model=mid, model_name=model["name"], backend="gpu", worker_id=st.id, worker_name=st.name,
                             gpu=st.gpu.get("name"), adapter=adapter, precision=chosen, attention=attention,
                             offload=offload, warm=bool(warm), vram_gb=need or None,
                             est_seconds=round(est, 1), est_cost=round(cost, 4),
                             reasons=reasons))
    return out


def _hosted_placements(model: dict[str, Any], fabric: dict[str, Any], req: RouteRequest, policy: GenerationPolicy,
                       rejected: list[dict[str, Any]]) -> list[Placement]:
    from agentic_core.models import catalog

    out: list[Placement] = []
    mid = model["id"]
    units = _units(req)
    forced = (os.getenv("MODEL_BACKEND") or "").strip().lower()
    for backend, why in catalog.available_backends(mid).items():
        if backend == "gpu":
            continue
        if forced in ("fal", "comfyui", "cloudflare", "gpu") and backend != forced:
            rejected.append({"model": mid, "backend": backend, "why": f"MODEL_BACKEND forces {forced}"})
            continue
        if why:
            rejected.append({"model": mid, "backend": backend, "why": why})
            continue
        if backend in HOSTED_PAID and not policy.allow_hosted:
            rejected.append({"model": mid, "backend": backend, "why": "paid hosted APIs are turned off in the limits"})
            continue
        reasons: list[str] = []
        learned = performance.lookup(mid, backend)
        if backend == "comfyui":
            est = float(fabric["speed"]) * units + float(fabric["load_seconds"]) * 0.5
            cost = 0.0
            reasons.append("your ComfyUI server (free per run)")
        elif backend == "cloudflare":
            est, cost = 5.0, 0.0
            reasons.append("Cloudflare free tier")
        elif backend == "fal":
            per_s = fabric.get("fal_usd_per_second")
            cost = float(per_s) * units if per_s else float(fabric.get("fal_usd") or 0.01) * units
            est = float(fabric.get("hosted_seconds") or 60) + (units * 5 if req.task != "image" else 0)
            reasons.append(f"fal.ai ≈ ${cost:.3f}")
        else:   # replicate / your hosted model
            d = model.get("definition") or {}
            cost = float(d.get("cost_usd") or (0.1 * units if req.task != "image" else 0.01))
            est = 60.0 if req.task != "image" else 10.0
            reasons.append(f"{backend} (estimated cost)")
        if learned and learned.get("unit_seconds"):
            est = float(learned["unit_seconds"]) * units
            reasons.append(f"speed measured over {learned['runs']} runs")
        out.append(Placement(model=mid, model_name=model["name"], backend=backend, est_seconds=round(est, 1),
                             est_cost=round(cost, 4), reasons=reasons))
    return out


def route(req: RouteRequest, statuses: list[WorkerStatus], policy: GenerationPolicy | None = None) -> RoutePlan:
    policy = policy or current()
    wq, ws, wc = WEIGHTS.get(policy.preference, WEIGHTS["balanced"])
    rejected: list[dict[str, Any]] = []
    placements: list[Placement] = []
    online = [s for s in statuses if s.online]
    for model in candidate_models(req):
        fabric = R.fabric_of(model)
        q, fit_why = fit_quality(model, fabric, req)
        here: list[Placement] = []
        for st in online:
            here += _gpu_placements(model, fabric, req, st, rejected)
        here += _hosted_placements(model, fabric, req, policy, rejected)
        for p in here:
            qe = q * R.PRECISION_QUALITY.get(p.precision or "bf16", 1.0)
            learned = performance.lookup(p.model, p.where)
            if learned:
                if learned.get("avg_qa") is not None:
                    qe += (float(learned["avg_qa"]) - 0.75) * 0.2
                ok = learned.get("ok", learned["runs"]) / max(1, learned["runs"])
                if ok < 1:
                    qe -= (1 - ok) * 0.3
                    p.reasons.append(f"{ok:.0%} of runs succeeded")
            if policy.max_cost_per_shot is not None and p.est_cost > policy.max_cost_per_shot:
                rejected.append({"model": p.model, "backend": p.backend, "worker": p.worker_name,
                                 "why": f"≈${p.est_cost:.2f} is over the ${policy.max_cost_per_shot:.2f} per-shot limit"})
                continue
            if policy.max_seconds_per_shot is not None and p.est_seconds > policy.max_seconds_per_shot:
                rejected.append({"model": p.model, "backend": p.backend, "worker": p.worker_name,
                                 "why": f"≈{p.est_seconds:.0f} s is over the {policy.max_seconds_per_shot:.0f} s per-shot limit"})
                continue
            speed_score = 1.0 / (1.0 + p.est_seconds / R.REF_SECONDS.get(req.task, 120.0))
            cost_score = 1.0 / (1.0 + p.est_cost / R.REF_COST.get(req.task, 0.3))
            p.quality = round(max(0.0, qe), 3)
            p.score = wq * p.quality + ws * speed_score + wc * cost_score
            if policy.preferred_model and p.model == policy.preferred_model:
                p.score += 0.25
                p.reasons.insert(0, "your preferred model")
            elif policy.fallback_model and p.model == policy.fallback_model:
                p.score += 0.05
                p.reasons.insert(0, "your fallback model")
            p.score = round(p.score, 4)
            p.reasons = fit_why + p.reasons
            placements.append(p)
    placements.sort(key=lambda p: (-p.score, p.est_seconds))
    return RoutePlan(request=req, policy=policy, placements=placements, rejected=rejected)


async def plan(req: RouteRequest, policy: GenerationPolicy | None = None, *, force: bool = False) -> RoutePlan:
    from agentic_core.model_fabric import workers

    await performance.refresh()
    return route(req, await workers.statuses(force=force), policy)
