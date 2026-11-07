"""Animation Studio server: ReelMimic's REST + SSE API over the job machine in jobs.py.

    python -m studio            → http://127.0.0.1:8020
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
import signal
import string
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from . import config, jobs as J
from .config import CONFIG, PROJECTS
from .llm import agent_kinds, agent_status, agents_info, pull_model, save_agent_settings
from .series import pipeline as series_pipeline
from .series.routes import router as series_router
from .explainer import pipeline as explainer_pipeline
from .explainer.routes import router as explainer_router
from .stickman import pipeline as stickman_pipeline
from .stickman.routes import router as stickman_router
from .skilllab import pipeline as skill_pipeline
from .skilllab.routes import router as skill_router
from .activity import router as activity_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    J.recover_orphans()   # a job still marked as working was cut off by a restart: say so
    series_pipeline.recover()
    explainer_pipeline.recover()
    stickman_pipeline.recover()
    skill_pipeline.recover()
    yield
    J.stop_all()
    for sid in list(series_pipeline._threads):
        series_pipeline.cancel(sid)


app = FastAPI(title="AVOS Animation Studio (ReelMimic in Python)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\]|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(series_router)
app.include_router(explainer_router)
app.include_router(stickman_router)
app.include_router(skill_router)
app.include_router(activity_router)
PROJECTS.mkdir(parents=True, exist_ok=True)
LANGS = ("zh-TW", "en", "zh-CN")


def err(status: int, msg: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": msg, **extra}, status_code=status)


def slug() -> str:
    return datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))


def safe_name(n: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", n or "file")[:120]


def is_url(s: str | None) -> bool:
    return bool(re.match(r"^https?://\S+$", (s or "").strip(), re.I))


def exists(jid: str) -> bool:
    return bool(re.match(r"^[\w-]+$", jid)) and (J.dir_of(jid) / "job.json").exists()


async def save_upload(f: UploadFile, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as out:
        while chunk := await f.read(1 << 20):
            out.write(chunk)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "repo": str(config.REPO), "repoPresent": config.REPO.is_dir(), "styles": str(config.STYLES), "projects": str(PROJECTS)}


@app.get("/api/agents")
async def agents() -> dict:
    return await agent_status()


@app.get("/api/agents/info")
async def agents_info_ep() -> dict:
    return await agents_info()


@app.post("/api/agents/settings")
async def agents_settings(req: Request) -> Any:
    body = await req.json() if (await req.body()) else {}
    try:
        save_agent_settings(body or {})
    except ValueError as e:
        return err(400, str(e))
    return await agents_info()


@app.post("/api/agents/pull")
async def agents_pull(req: Request) -> Any:
    body = await req.json()
    model = str((body or {}).get("model") or "").strip()
    if not model:
        return err(400, "model?")
    J.spawn(pull_model(model))
    return {"ok": True}


@app.get("/api/config")
async def get_config() -> dict:
    return CONFIG


@app.get("/api/projects")
async def projects() -> list:
    return J.list_jobs()


@app.post("/api/projects")
async def create(req: Request) -> Any:
    form = await req.form()
    url = str(form.get("url") or "")
    brief = str(form.get("brief") or "")
    title = str(form.get("title") or "")
    agent = str(form.get("agent") or "") or (await agents_info())["default"]
    lang = str(form.get("lang") or "")
    lang = lang if lang in LANGS else "en"
    ref = form.get("reference")
    ref = ref if hasattr(ref, "read") and getattr(ref, "filename", None) else None
    if not ref and not is_url(url):
        return err(400, "請上傳參考影片或貼上影片連結")
    if agent not in agent_kinds():
        return err(400, f"agent must be one of {', '.join(agent_kinds())}")
    if "�" in brief + title:
        return err(400, "需求文字編碼錯誤（請用 UTF-8 送出）")
    try:
        settings = {k: v for k, v in J.clean_rounds({k: form.get(k) for k in config.ROUND_KEYS if k in form}).items() if v is not None}
    except ValueError as e:
        return err(400, str(e))
    jid = slug()
    ext = Path(ref.filename).suffix.lower() if ref else ""
    reference = {"type": "file", "src": "inputs/reference" + (ext or ".mp4")} if ref else {"type": "url", "src": url.strip()}
    from .director.pre import title_from_brief
    J.create_job(jid, (title or title_from_brief(brief) or "Untitled")[:60], agent, brief, reference, lang, settings)
    if ref:
        await save_upload(ref, J.dir_of(jid) / reference["src"])
    for f in form.getlist("inputs"):
        if hasattr(f, "read") and getattr(f, "filename", None):
            await save_upload(f, J.dir_of(jid) / "inputs" / safe_name(f.filename))
    J.spawn(J.start(jid))
    return {"id": jid}


@app.get("/api/projects/{jid}")
async def project(jid: str) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    return J.snapshot(jid)


@app.post("/api/projects/{jid}/inputs")
async def add_inputs(jid: str, req: Request) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    attach = req.query_params.get("to") == "attachments"
    sub = "inputs/attachments" if attach else "inputs"
    (J.dir_of(jid) / sub).mkdir(parents=True, exist_ok=True)
    form = await req.form()
    saved = []
    for f in form.getlist("inputs"):
        if not (hasattr(f, "read") and getattr(f, "filename", None)):
            continue
        name = (format(int(datetime.now().timestamp() * 1000), "x") + "_" if attach else "") + safe_name(f.filename)
        await save_upload(f, J.dir_of(jid) / sub / name)
        saved.append(f"{sub}/{name}")
    for_ = req.query_params.get("for")
    if not attach and for_:
        J.provide_input(jid, for_, saved)
    elif not attach:
        J.spawn(J.align_if_ready(jid))
    J.touch(jid)
    return {**J.snapshot(jid), "saved": saved}


def _guard_busy(jid: str, allow_pre_plan_message: bool = False) -> JSONResponse | None:
    if not exists(jid):
        return err(404, "no such project")
    if J.busy(jid) and not (allow_pre_plan_message and J.load(jid)["stage"] in J.PRE_PLAN):
        return err(409, J.L(jid, "agent 正在工作中，請等這一輪完成", "The agent is working — wait for this turn to finish"))
    return None


@app.post("/api/projects/{jid}/message")
async def message(jid: str, req: Request) -> Any:
    body = await req.json()
    text, meta = (body or {}).get("text") or "", (body or {}).get("meta") or {}
    if not text.strip() and not meta.get("attachments"):
        return err(400, "empty")
    if (bad := _guard_busy(jid, allow_pre_plan_message=True)):
        return bad
    J.spawn(J.message(jid, text, meta))
    return {"ok": True}


@app.post("/api/projects/{jid}/approve")
async def approve(jid: str) -> Any:
    if (bad := _guard_busy(jid)):
        return bad
    open_ = J.open_inputs(jid)
    if open_:
        return err(409, J.L(jid, "還有需要你提供或略過的素材：" + "、".join(r.get("label") or r["id"] for r in open_),
                            "Still needs your input or a skip: " + ", ".join(r.get("label") or r["id"] for r in open_)), open=open_)
    J.spawn(J.approve(jid))
    return {"ok": True}


@app.post("/api/projects/{jid}/lyrics")
async def lyrics(jid: str, req: Request) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    text = ((await req.json()) or {}).get("text", "").strip()
    if not text:
        return err(400, "請貼上歌詞文字")
    return await J.save_lyrics(jid, text)


@app.post("/api/projects/{jid}/waive")
async def waive(jid: str, req: Request) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    J.waive(jid, str(((await req.json()) or {}).get("input") or ""))
    return J.snapshot(jid)


@app.post("/api/projects/{jid}/unwaive")
async def unwaive(jid: str, req: Request) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    J.unwaive(jid, str(((await req.json()) or {}).get("input") or ""))
    return J.snapshot(jid)


def _act(fn: Any) -> Any:
    async def handler(jid: str) -> Any:
        if (bad := _guard_busy(jid)):
            return bad
        J.spawn(fn(jid))
        return {"ok": True}
    return handler


app.post("/api/projects/{jid}/resume")(_act(J.resume))
app.post("/api/projects/{jid}/accept")(_act(J.accept))
app.post("/api/projects/{jid}/retry")(_act(J.retry))
app.post("/api/projects/{jid}/critique")(_act(J.critique))


@app.post("/api/projects/{jid}/settings")
async def settings(jid: str, req: Request) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    try:
        return J.set_rounds(jid, (await req.json()) or {})
    except ValueError as e:
        return err(400, str(e))


@app.post("/api/projects/{jid}/finish")
async def ai_finish(jid: str, req: Request) -> Any:
    """AI finish: the finished film through an open video model (Wan VACE, Wan 2.2 Animate, SCAIL-2, LTX-2.3)."""
    from . import finish
    if not exists(jid):
        return err(404, "no such project")
    body = await req.json() if (await req.body()) else {}
    model = str((body or {}).get("model") or "")
    why = finish.check(J.dir_of(jid), model)
    if why:
        return err(409 if "running" in why or "first" in why else 400, why)
    return {"ok": True, "finish": finish.start(J.dir_of(jid), model)}


@app.post("/api/projects/{jid}/cancel")
async def cancel(jid: str) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    J.cancel(jid)
    return {"ok": True}


@app.get("/api/projects/{jid}/events")
async def events(jid: str, req: Request) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    q = J.bus.subscribe(jid)

    async def gen():
        try:
            yield ": hello\n\n"
            while True:
                if await req.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), 20)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            J.bus.unsubscribe(jid, q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/files/{jid}/{path:path}")
async def files(jid: str, path: str) -> Any:
    if not exists(jid):
        return err(404, "no such project")
    base = J.dir_of(jid).resolve()
    p = (base / path).resolve()
    if not str(p).startswith(str(base) + ("/" if "/" in str(base) else "\\")) and p.parent != base:
        return Response(status_code=404)
    if not p.is_file():
        return Response(status_code=404)
    return FileResponse(p, headers={"Cache-Control": "no-cache"})


def main() -> None:
    import uvicorn
    host = __import__("os").environ.get("STUDIO_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=config.PORT, log_level="warning")
