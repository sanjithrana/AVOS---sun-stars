"""The Model Fabric: routing over GPU workers and hosted APIs, VRAM / precision checks, limits, learned performance."""
import asyncio
import json

import httpx
import pytest

from agentic_core import settings_store
from agentic_core.model_fabric import performance, policy, router, workers
from agentic_core.model_fabric.policy import GenerationPolicy
from agentic_core.model_fabric.router import RouteRequest, route
from agentic_core.model_fabric.workers import WorkerStatus
from agentic_core.models import catalog

ALL = ["z-image", "qwen-image", "flux-schnell", "wan-2.2", "ltx-2.3", "wan-vace", "longcat-avatar", "infinitetalk"]


def worker(name="RTX 4090 box", gpu="NVIDIA GeForce RTX 4090", vram=24, free=None, cc_fp8=True, fp4=False, cost=0.0,
           loaded=(), queue=0, models=ALL, precisions=("bf16", "fp8", "int8", "fp4", "int4"), attention="sage2", wid=None):
    return WorkerStatus(
        id=wid or name.lower().replace(" ", "-"), name=name, url="http://w", online=True, cost_per_hour=cost,
        report={"gpu": {"name": gpu, "vram_gb": vram, "free_vram_gb": vram if free is None else free},
                "supports": {"bf16": True, "fp8": cc_fp8, "fp4": fp4, "int8": True},
                "adapters": {"diffusers": {"ready": True, "models": list(models), "precisions": list(precisions),
                                           "attention": attention, "offload": True}},
                "loaded_models": [{"model": m, "adapter": "diffusers", "precision": p} for m, p in loaded],
                "queue_depth": queue, "running": None})


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    for k in ("FAL_KEY", "COMFYUI_URL", "MODEL_BACKEND", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "GPU_WORKER_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AVOS_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("COMFYUI_WORKFLOW_DIR", str(tmp_path / "wf"))
    workers.forget()
    performance.update({})
    yield
    settings_store.save(settings_store._empty())
    workers.forget()
    performance.update({})


def best(plan):
    return plan.placements[0]


def test_hosted_only_routes_like_before(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    plan = route(RouteRequest(task="video", seconds=4), [])
    assert best(plan).model == "wan-2.2" and best(plan).backend == "fal"
    assert best(route(RouteRequest(task="video", seconds=14), [])).model == "ltx-2.3"
    assert best(route(RouteRequest(task="image", prompt="a poster titled 'Volcanoes'"), [])).model == "qwen-image"
    assert best(route(RouteRequest(task="avatar", seconds=40), [])).model == "infinitetalk"


def test_gpu_worker_picks_a_precision_that_fits_its_vram():
    plan = route(RouteRequest(task="video", seconds=5, models=["wan-2.2"]), [worker()])
    p = best(plan)
    assert (p.backend, p.adapter, p.precision, p.attention) == ("gpu", "diffusers", "fp8", "sage2")
    assert not p.offload and p.vram_gb == 16 and "loads in" in " ".join(p.reasons)
    # a 12 GB card: bf16/fp8/int8 don't fit, fp4 isn't native on Ada → int4
    small = best(route(RouteRequest(task="video", models=["wan-2.2"]), [worker(vram=12)]))
    assert small.precision == "int4" and not small.offload
    # an older card without fp8 never gets fp8
    ampere = best(route(RouteRequest(task="video", models=["wan-2.2"]), [worker(gpu="NVIDIA GeForce RTX 3090", cc_fp8=False)]))
    assert ampere.precision == "int8"


def test_blackwell_uses_fp4_and_too_small_gpus_are_rejected_or_offload():
    rtx5090 = worker(gpu="NVIDIA GeForce RTX 5090", vram=32, fp4=True)
    assert best(route(RouteRequest(task="video", models=["ltx-2.3"]), [rtx5090])).precision == "fp8"   # 26 GB fits
    b = best(route(RouteRequest(task="video", models=["ltx-2.3"]), [worker(gpu="NVIDIA RTX PRO 4000 Blackwell", vram=24, fp4=True)]))
    assert b.precision == "fp4" and not b.offload                                                      # 15 GB at fp4
    b16 = best(route(RouteRequest(task="video", models=["ltx-2.3"]), [worker(gpu="NVIDIA GeForce RTX 5080", vram=16, fp4=True)]))
    assert b16.precision == "fp4" and b16.offload                                                      # 15 GB > 16 - reserve
    tiny = route(RouteRequest(task="video", models=["ltx-2.3"]), [worker(gpu="NVIDIA GeForce RTX 3060", vram=12,
                                                                          cc_fp8=False, precisions=("bf16",))])
    assert not tiny.placements and "needs about" in tiny.rejected[0]["why"]
    off = best(route(RouteRequest(task="video", models=["wan-2.2"]), [worker(vram=8, precisions=("bf16", "int8"))]))
    assert off.offload and "CPU offload" in " ".join(off.reasons)


def test_warm_model_and_queue_change_the_choice():
    cold, warm = worker(name="Cold", wid="cold"), worker(name="Warm", wid="warm", loaded=[("wan-2.2", "fp8")])
    p = best(route(RouteRequest(task="video", models=["wan-2.2"]), [cold, warm]))
    assert p.worker_id == "warm" and p.warm and "already loaded" in p.reasons
    busy = worker(name="Busy", wid="busy", loaded=[("wan-2.2", "fp8")], queue=3)
    assert best(route(RouteRequest(task="video", models=["wan-2.2"]), [cold, busy])).worker_id == "cold"


def test_preference_trades_your_gpu_against_fal(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    rented = worker(cost=0.69, gpu="NVIDIA GeForce RTX 3090", cc_fp8=False)
    req = RouteRequest(task="video", seconds=5, models=["wan-2.2"])
    assert best(route(req, [rented], GenerationPolicy(preference="cost"))).backend == "gpu"
    assert best(route(req, [rented], GenerationPolicy(preference="speed"))).backend == "fal"


def test_limits_reject_and_explain(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    req = RouteRequest(task="video", seconds=8)
    plan = route(req, [], GenerationPolicy(max_cost_per_shot=0.1))
    assert not plan.placements and all("per-shot limit" in r["why"] for r in plan.rejected if r["backend"] == "fal")
    plan = route(req, [], GenerationPolicy(allow_hosted=False))
    assert not plan.placements and any("turned off" in r["why"] for r in plan.rejected)
    slow = route(RouteRequest(task="video", seconds=8, models=["wan-2.2"]), [worker(gpu="NVIDIA GeForce RTX 3060", vram=12, cc_fp8=False)],
                 GenerationPolicy(max_seconds_per_shot=60))
    assert not slow.placements and "s per-shot limit" in slow.rejected[-1]["why"]


def test_preferred_model_wins(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    p = best(route(RouteRequest(task="video", seconds=4), [], GenerationPolicy(preferred_model="ltx-2.3")))
    assert p.model == "ltx-2.3" and p.reasons[0] == "your preferred model"


def test_measured_performance_replaces_estimates_and_penalises_failures():
    w = worker()
    est = best(route(RouteRequest(task="video", seconds=5, models=["wan-2.2"]), [w])).est_seconds
    performance.update({performance.key("wan-2.2", "NVIDIA GeForce RTX 4090"): {"runs": 5, "ok": 5, "unit_seconds": 4.0}})
    measured = best(route(RouteRequest(task="video", seconds=5, models=["wan-2.2"]), [w]))
    assert measured.est_seconds < est and "measured over 5 runs" in " ".join(measured.reasons)
    performance.update({performance.key("wan-2.2", "NVIDIA GeForce RTX 4090"): {"runs": 4, "ok": 2, "avg_qa": 0.5}})
    flaky = best(route(RouteRequest(task="video", seconds=5, models=["wan-2.2"]), [w]))
    assert flaky.quality < measured.quality and "50% of runs succeeded" in flaky.reasons


def test_policy_resolution_from_settings_and_project():
    settings_store.set_fabric({"preference": "quality", "max_cost_per_shot": 0.5, "max_attempts": 4})
    pol = policy.resolve({"max_cost_per_shot": None, "preference": "cost"})
    assert pol.preference == "cost" and pol.max_cost_per_shot is None and pol.max_attempts == 4
    with policy.use(pol):
        assert policy.current().preference == "cost"
    assert policy.current().preference == "quality"
    with pytest.raises(ValueError):
        settings_store.clean_policy({"preference": "cheapest"})
    with pytest.raises(ValueError):
        settings_store.clean_policy({"max_attempts": 0})


def test_workers_in_settings_and_catalog_readiness(monkeypatch):
    settings_store.upsert_worker({"name": "Home 4090", "url": "http://10.0.0.5:8700/", "cost_per_hour": "0"})
    w = settings_store.workers()[0]
    assert w["id"] == "10-0-0-5-8700" and w["url"] == "http://10.0.0.5:8700"
    with pytest.raises(ValueError):
        settings_store.upsert_worker({"url": "ftp://x"})
    assert catalog.available_backends("wan-2.2")["gpu"] == "No GPU worker is online."   # asked now: unreachable
    st = worker(wid=w["id"], models=["wan-2.2"])
    workers._cache[w["id"]] = (1e12, st)
    assert catalog.available_backends("wan-2.2")["gpu"] is None and catalog.backend_for("wan-2.2") == "gpu"
    assert "No online GPU worker can run it" in catalog.available_backends("qwen-image")["gpu"]
    settings_store.delete_worker(w["id"])
    assert "gpu" not in catalog.available_backends("wan-2.2")


def test_worker_status_fetch_and_token(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"gpu": {"name": "NVIDIA H100 80GB HBM3", "vram_gb": 80}, "adapters": {}, "cost_per_hour": 2.5})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    settings_store.set_env({"GPU_WORKER_TOKEN": "tok"})
    st = asyncio.run(workers.fetch({"id": "h100", "url": "http://h100:8700", "name": "H100"}, force=True))
    assert st.online and st.gpu["vram_gb"] == 80 and st.cost_per_hour == 2.5 and seen["auth"] == "Bearer tok"


def test_plan_serialises_for_the_api(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    d = route(RouteRequest(task="image", prompt="a fox"), [worker()]).as_dict()
    json.dumps(d)
    assert d["placements"][0]["where"] and {"model", "backend", "score", "reasons", "est_seconds", "est_cost"} <= set(d["placements"][0])


# ---------- GPU Scheduler (dispatch ledger, priorities, warm-up) ----------
from agentic_core.model_fabric import dispatch, scheduler  # noqa: E402


@pytest.fixture
def ledger():
    dispatch.clear()
    yield
    dispatch.clear()


def test_parallel_jobs_spread_over_gpus_and_stick_to_warm_models(ledger):
    a = worker(name="GPU A", wid="a")
    b = worker(name="GPU B", wid="b")
    req = RouteRequest(task="video", seconds=5, models=["wan-2.2"])
    first = best(route(req, [a, b]))
    with dispatch.reserve(first):
        second = best(route(req, [a, b]))
        # the same model is on its way to the first GPU: no second load there, but it's busy for a while;
        # the other GPU is free but must load the model. Either way the estimate shows the queue.
        assert second.worker_id != first.worker_id or "loading for an earlier shot" in second.reasons
        with dispatch.reserve(second), dispatch.reserve(first):
            third = best(route(req, [a, b]))
            busy = {p.worker_id: p.est_seconds for p in route(req, [a, b]).placements}
            assert busy["a"] > 0 and busy["b"] > 0
            assert third.est_seconds >= min(first.est_seconds, second.est_seconds)
    assert dispatch.inflight("a") == [] and dispatch.inflight("b") == []


def test_urgent_jobs_ignore_normal_work_in_the_wait_estimate(ledger):
    a = worker(name="GPU A", wid="a", loaded=[("wan-2.2", "fp8")])
    req = RouteRequest(task="video", seconds=5, models=["wan-2.2"])
    p = best(route(req, [a]))
    with dispatch.reserve(p), dispatch.reserve(p):
        normal = best(route(req, [a])).est_seconds
        with dispatch.use_priority(dispatch.URGENT):
            urgent = best(route(req, [a])).est_seconds
            assert dispatch.current_priority() == 0
    assert urgent < normal


def test_warm_up_notes_expire(ledger, monkeypatch):
    t = dispatch.note("a", "ltx-2.3", "diffusers", "fp8", seconds=0.05, ttl=0.05)
    assert dispatch.on_the_way("a") == {("ltx-2.3", "diffusers"): "fp8"} and t in dispatch.inflight("a")
    import time as _t
    _t.sleep(0.08)
    assert dispatch.inflight("a") == [] and dispatch.snapshot() == {}


def test_prewarm_loads_each_model_once_on_different_gpus(ledger, monkeypatch):
    settings_store.upsert_worker({"id": "wa", "name": "A", "url": "http://a"})
    settings_store.upsert_worker({"id": "wb", "name": "B", "url": "http://b"})
    sts = [worker(name="A", wid="wa"), worker(name="B", wid="wb", loaded=[("z-image", "bf16")])]

    async def fake_statuses(force=False):
        return sts
    monkeypatch.setattr(workers, "statuses", fake_statuses)
    sent = []

    def handler(req):
        sent.append((str(req.url), json.loads(req.content)))
        return httpx.Response(200, json={"id": "j"})
    real = httpx.AsyncClient
    monkeypatch.setattr(scheduler.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    done = asyncio.run(scheduler.prewarm([RouteRequest(task="image", models=["z-image"]),
                                         RouteRequest(task="video", seconds=5, models=["wan-2.2"])]))
    assert done[0] == {"model": "z-image", "worker": "B", "already": True}       # already loaded on B: nothing sent
    assert len(sent) == 1 and sent[0][0] == "http://a/models/load" and sent[0][1]["model"] == "wan-2.2"
    assert ("wan-2.2", "diffusers") in dispatch.on_the_way("wa")


def test_a_cpu_worker_runs_what_fits_in_ram_plus_page_file():
    """An Intel PC without a GPU (ComfyUI --cpu): memory is RAM + page file; it's slow, so it's ranked as slow, and a
    model that doesn't fit says to grow the page file."""
    def cpu(swap):
        w = worker(name="Intel PC", gpu="Intel Core i7 (CPU)", vram=16 + swap, precisions=("bf16", "fp8"))
        w.report["gpu"].update(device="cpu", ram_gb=16, swap_gb=swap, max_side=512)
        w.report["adapters"]["diffusers"].update(device="cpu", offload=False)
        return w
    p = best(route(RouteRequest(task="video", seconds=5, models=["ltx-2.3"]), [cpu(48)]))
    assert p.precision == "fp8" and not p.offload and "16 GB RAM + 48 GB page file" in " ".join(p.reasons)
    fast = best(route(RouteRequest(task="video", seconds=5, models=["ltx-2.3"]), [worker(gpu="NVIDIA GeForce RTX 5090", vram=32)]))
    assert p.est_seconds > 20 * fast.est_seconds
    small = route(RouteRequest(task="video", seconds=5, models=["ltx-2.3"]), [cpu(0)])
    assert not small.placements and "page file" in small.rejected[0]["why"]
