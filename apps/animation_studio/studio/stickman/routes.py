"""Stickman Studio REST API (mounted at /api/stickman; the desktop reaches it through /studio-api).

    GET    /api/stickman                         your projects
    POST   /api/stickman                         {event?, interest?, aspect?, language?, crew?, auto?, tone?}  (no event → eight topic ideas to choose from)
    GET    /api/stickman/{id}                    everything the page shows
    POST   /api/stickman/{id}/pick               {index}  choose one of the eight ideas → the whole production package
    POST   /api/stickman/{id}/more-topics        {note?}  eight new ideas
    PATCH  /api/stickman/{id}                    {narration: {"1": "..."}} edit narration · {tone?, auto?, voice?, models?}
    POST   /api/stickman/{id}/approve            ✔ the reference sheets → scene images, animation, voice, final video
    POST   /api/stickman/{id}/continue | /cancel
    POST   /api/stickman/{id}/clips/{n}          {what: scene|video, note?}  one clip again
    GET    /api/stickman/{id}/package            the written package (Markdown); GET /files/{path}: pictures, clips, final.mp4
    DELETE /api/stickman/{id}
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from . import package, pipeline, spec, store

router = APIRouter(prefix="/api/stickman")


def err(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


async def _body(req: Request) -> dict:
    try:
        return (await req.json()) or {} if await req.body() else {}
    except ValueError:
        return {}


def _view(p: dict) -> dict:
    return {**p, "busy": pipeline.busy(p["id"]), "stages": [{"id": s, "label": pipeline.LABELS[s]} for s in pipeline.STAGES]}


def _need(pid: str) -> JSONResponse | None:
    return None if store.exists(pid) else err(404, "no such project")


@router.get("")
def listing() -> list[dict]:
    return store.listing()


@router.post("")
async def create(req: Request) -> Any:
    from ..llm import agent_kinds, default_agent
    b = await _body(req)
    raw = "\n".join(" ".join(ln.split()) for ln in str(b.get("event") or "").splitlines()).strip()
    source = raw[:6000] if len(raw) > 140 else ""          # a pasted article, copy or full script: the treatment keeps its meaning
    event = (raw.split("\n")[0].split(". ")[0] if source else raw)[:140]
    aspect = b.get("aspect") if b.get("aspect") in spec.ASPECTS else "9:16"
    crew = b.get("crew") if b.get("crew") in agent_kinds() else default_agent()
    pid = store.new_id()
    tone = str(b.get("tone") or "engaging, respectful, clear")[:120]
    from . import styles
    try:
        top = 30 if styles.get(b.get("style")).get("autopilot") else 12      # Autopilot looks are long-form-first (up to 5 minutes here)
        clips = int(max(3, min(top, round(float(b.get("seconds") or 60) / spec.CLIP_SECONDS))))
    except (TypeError, ValueError):
        clips = 6
    st = b.get("style") if b.get("style") in styles.BY_ID else styles.DEFAULT
    p = {"id": pid, "title": event or "Stickman video", "event": event, "style": st, "source_text": source, "interest": str(b.get("interest") or "")[:200], "aspect": aspect,
         "language": str(b.get("language") or "en"), "crew": crew, "auto": bool(b.get("auto")), "tone": tone, "voice": "female" if b.get("voice") == "female" else "male",
         "models": b.get("models") if isinstance(b.get("models"), dict) else {}, "local_only": bool(b.get("local_only")), "status": "working", "stage": "brief" if event else "topics",
         "clip_count": clips, "seconds": clips * spec.CLIP_SECONDS, "length_set": "seconds" in b, "topics": None, "project": None, "brief": None, "story": None, "roster": None, "clips": [], "assets": {}, "log": [],
         "createdAt": store.now(), "updatedAt": store.now()}
    if event:
        p["project"] = {"title": event, "date_place": "", "premise": source[:600], "tone": tone, "scope": "", "opening_visual": "", "ending": ""}
    store.save(p)
    pipeline.start(pid, "brief" if event else "topics")
    return _view(p)


@router.get("/styles")
def style_list() -> Any:
    from . import styles
    return {"styles": styles.public(), "default": styles.DEFAULT}


@router.get("/{pid}")
def get(pid: str) -> Any:
    return _need(pid) or _view(store.load(pid))


@router.post("/{pid}/pick")
async def pick(pid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    if pipeline.busy(pid):
        return err(409, "Busy.")
    try:
        pipeline.pick(pid, int((await _body(req)).get("index", -1)))
    except (ValueError, TypeError):
        return err(400, "Pick one of the ideas on the page.")
    pipeline.start(pid, "brief")
    return _view(store.load(pid))


@router.post("/{pid}/more-topics")
async def more(pid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    if pipeline.busy(pid):
        return err(409, "Busy.")
    note = str((await _body(req)).get("note") or "")[:300]
    store.update(pid, lambda p: p.update(note=note, project=None, topics=None))
    pipeline.start(pid, "topics")
    return _view(store.load(pid))


@router.patch("/{pid}")
async def patch(pid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    if pipeline.busy(pid):
        return err(409, "Busy; stop it first.")
    b = await _body(req)
    def f(p: dict) -> None:
        if "auto" in b:
            p["auto"] = bool(b["auto"])
        if b.get("voice") in ("male", "female"):
            p["voice"] = b["voice"]
        if isinstance(b.get("models"), dict):
            p["models"] = b["models"]
        if "local_only" in b:
            p["local_only"] = bool(b["local_only"])
        if isinstance(b.get("narration"), dict) and p.get("story"):
            for k, v in b["narration"].items():
                try:
                    c = p["story"]["clips"][int(k) - 1]
                except (ValueError, IndexError):
                    continue
                c["narration"] = " ".join(str(v).split())[:400] or c["narration"]
            for c in p.get("clips") or []:
                c["narration_warning"] = spec.narration_warning(p["story"]["clips"][c["n"] - 1]["narration"])
    store.update(pid, f)
    (store.pdir(pid) / "package.md").write_text(package.build(store.load(pid)), "utf-8") if store.load(pid).get("clips") else None
    return _view(store.load(pid))


@router.post("/{pid}/approve")
def approve(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if p.get("status") != "waiting":
        return err(409, "Nothing is waiting for approval.")
    if p.get("stage") == "topics":
        return err(400, "Pick one of the ideas first.")
    pipeline.start(pid, pipeline.next_stage(p))
    return _view(store.load(pid))


@router.post("/{pid}/continue")
def cont(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if not pipeline.start(pid, p.get("stage") or "topics"):
        return err(409, "Already running.")
    return _view(store.load(pid))


@router.post("/{pid}/cancel")
def cancel(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    pipeline.cancel(pid)
    return {"ok": True}


@router.post("/{pid}/clips/{n}")
async def clip_again(pid: str, n: int, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if not 1 <= n <= len(p.get("clips") or []):
        return err(404, "no such clip")
    b = await _body(req)
    if not pipeline.redo_clip(pid, n, "scene" if b.get("what") == "scene" else "video", str(b.get("note") or "")[:300]):
        return err(409, "Busy; stop it first.")
    return _view(store.load(pid))


@router.get("/{pid}/package")
def pkg(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if not p.get("clips"):
        return err(404, "The package is written once the clip prompts exist.")
    return PlainTextResponse(package.build(p), headers={"Content-Disposition": f'attachment; filename="{pid}-production-package.md"'})


@router.get("/{pid}/files/{path:path}")
def files(pid: str, path: str) -> Any:
    f = store.file_path(pid, path)
    return FileResponse(f) if f else err(404, "no such file")


@router.delete("/{pid}")
def delete(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    pipeline.cancel(pid)
    store.delete(pid)
    return {"ok": True}
